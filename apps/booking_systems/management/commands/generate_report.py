"""
Management command: generate_report

Usage:
    python manage.py generate_report \\
        --booking_system_id=1 \\
        --start_date=2026-01-01 \\
        --end_date=2026-03-07

All aggregations use Django ORM (Sum, Count, TruncMonth, annotate).
Total DB queries: 4 — one per section, no N+1.
"""

import json
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Avg, Count, DecimalField, Q, Sum
from django.db.models.functions import TruncMonth

from apps.booking_systems.models import Appointment, BookingSystem


def _float(value):
    """Convert Decimal / None → float for JSON output."""
    if value is None:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


class Command(BaseCommand):
    help = "Generate an analytics report for a booking system over a date range."

    def add_arguments(self, parser):
        parser.add_argument(
            "--booking_system_id",
            type=int,
            required=True,
            help="ID of the BookingSystem to report on.",
        )
        parser.add_argument(
            "--start_date",
            type=str,
            required=True,
            help="Report start date (YYYY-MM-DD, inclusive).",
        )
        parser.add_argument(
            "--end_date",
            type=str,
            required=True,
            help="Report end date (YYYY-MM-DD, inclusive).",
        )

    def handle(self, *args, **options):
        bs_id      = options["booking_system_id"]
        start_date = options["start_date"]
        end_date   = options["end_date"]

        # Validate booking system exists
        try:
            bs = BookingSystem.objects.get(pk=bs_id)
        except BookingSystem.DoesNotExist:
            raise CommandError(f"BookingSystem with id={bs_id} does not exist.")

        # ── Base queryset (reused by all four queries) ─────────────────────
        qs = Appointment.objects.filter(
            booking_system_id=bs_id,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date,
        )

        # ── Query 1: Summary ───────────────────────────────────────────────
        summary_agg = qs.aggregate(
            total_appointments=Count("id"),
            unique_customers=Count("customer_id", distinct=True),
            total_revenue=Sum("service__price"),
            avg_appointment_value=Avg("service__price"),
        )

        total_appointments = summary_agg["total_appointments"] or 0
        total_revenue      = _float(summary_agg["total_revenue"])
        avg_value          = _float(summary_agg["avg_appointment_value"])
        unique_customers   = summary_agg["unique_customers"] or 0

        # ── Query 2: Monthly breakdown ─────────────────────────────────────
        monthly_rows = (
            qs
            .annotate(month=TruncMonth("start_time"))
            .values("month")
            .annotate(
                appointments=Count("id"),
                unique_customers=Count("customer_id", distinct=True),
                revenue=Sum("service__price"),
            )
            .order_by("month")
        )

        monthly_breakdown = [
            {
                "month": row["month"].strftime("%Y-%m"),
                "appointments": row["appointments"],
                "unique_customers": row["unique_customers"],
                "revenue": _float(row["revenue"]),
            }
            for row in monthly_rows
        ]

        # ── Query 3: Top 5 providers by revenue ───────────────────────────
        provider_rows = (
            qs
            .values("provider__id", "provider__first_name", "provider__last_name")
            .annotate(
                total_appointments=Count("id"),
                total_revenue=Sum("service__price"),
            )
            .order_by("-total_revenue")[:5]
        )

        top_providers = [
            {
                "name": f"{r['provider__first_name']} {r['provider__last_name']}".strip(),
                "total_appointments": r["total_appointments"],
                "total_revenue": _float(r["total_revenue"]),
            }
            for r in provider_rows
        ]

        # ── Query 4: Top 5 services by revenue ────────────────────────────
        service_rows = (
            qs
            .values("service__id", "service__name")
            .annotate(
                times_booked=Count("id"),
                total_revenue=Sum("service__price"),
            )
            .order_by("-total_revenue")[:5]
        )

        top_services = [
            {
                "name": r["service__name"],
                "times_booked": r["times_booked"],
                "total_revenue": _float(r["total_revenue"]),
            }
            for r in service_rows
        ]

        # ── Assemble report ────────────────────────────────────────────────
        report = {
            "booking_system": bs.name,
            "period": f"{start_date} to {end_date}",
            "summary": {
                "total_appointments":    total_appointments,
                "unique_customers":      unique_customers,
                "total_revenue":         total_revenue,
                "avg_appointment_value": avg_value,
            },
            "monthly_breakdown": monthly_breakdown,
            "top_providers":     top_providers,
            "top_services":      top_services,
        }

        self.stdout.write(json.dumps(report, indent=2))
