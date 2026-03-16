"""
DataSyncHandler — pulls data from Easy!Appointments into Django models.

Design rules:
- update_or_create on (booking_system, external_id) → idempotent upserts
- null coercion: CharField/TextField always receive "" instead of None
- Each record is wrapped in transaction.atomic(); errors are logged and skipped
- Appointments: FK objects resolved by external_id; missing FK → skip + warn
"""

import logging
import traceback
from datetime import timezone as tz

from django.db import transaction
from django.utils import timezone

from .client import BookingSystemClient
from .exceptions import BookingAPIError
from .models import Appointment, BookingSystem, Customer, Provider, Service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _str(value, default: str = "") -> str:
    """Coerce None → default for CharField / TextField."""
    if value is None:
        return default
    return str(value).strip()


def _decimal(value, default="0.00"):
    """Coerce None → default for DecimalField."""
    if value is None:
        return default
    return value


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class DataSyncHandler:
    """
    Syncs data from an external booking system into our Django models.

    Usage::

        handler = DataSyncHandler(booking_system)
        summary = handler.sync_all()
        # → {"providers": 6, "customers": 16, "services": 13, "appointments": 20}
    """

    def __init__(self, booking_system: BookingSystem) -> None:
        self.booking_system = booking_system
        creds = booking_system.credentials
        self.client = BookingSystemClient(
            base_url=booking_system.base_url,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
        )

    # ------------------------------------------------------------------
    # Public sync methods
    # ------------------------------------------------------------------

    def sync_all(self) -> dict:
        """
        Run full sync in required order:
            providers → customers → services → appointments

        Returns a summary dict of counts.
        Raises on client-level failure (auth, network); individual record
        errors are logged and skipped.
        """
        logger.info("[BookingSystem %d] Starting full sync", self.booking_system.id)
        summary = {
            "providers":    self.sync_providers(),
            "customers":    self.sync_customers(),
            "services":     self.sync_services(),
            "appointments": self.sync_appointments(),
        }
        logger.info("[BookingSystem %d] Full sync complete: %s", self.booking_system.id, summary)
        return summary

    def sync_providers(self) -> int:
        """Fetch and upsert all providers. Returns count of synced records."""
        records = self.client.get_providers()
        count = 0
        for raw in records:
            external_id = str(raw["id"])
            try:
                with transaction.atomic():
                    Provider.objects.update_or_create(
                        booking_system=self.booking_system,
                        external_id=external_id,
                        defaults={
                            "first_name": _str(raw.get("firstName")),
                            "last_name":  _str(raw.get("lastName")),
                            "email":      _str(raw.get("email")),
                            "phone":      _str(raw.get("phone") or raw.get("mobile")),
                            "extra_data": {
                                k: v for k, v in raw.items()
                                if k not in {"id", "firstName", "lastName", "email", "phone", "mobile"}
                            },
                        },
                    )
                count += 1
            except Exception:
                logger.error(
                    "[BookingSystem %d] Failed to sync provider external_id=%s:\n%s",
                    self.booking_system.id, external_id, traceback.format_exc(),
                )
        logger.info("[BookingSystem %d] Synced %d providers", self.booking_system.id, count)
        return count

    def sync_customers(self) -> int:
        """Fetch and upsert all customers. Returns count of synced records."""
        records = self.client.get_customers()
        count = 0
        for raw in records:
            external_id = str(raw["id"])
            try:
                with transaction.atomic():
                    Customer.objects.update_or_create(
                        booking_system=self.booking_system,
                        external_id=external_id,
                        defaults={
                            "first_name": _str(raw.get("firstName")),
                            "last_name":  _str(raw.get("lastName")),
                            "email":      _str(raw.get("email")),
                            "phone":      _str(raw.get("phone") or raw.get("mobile")),
                            "extra_data": {
                                k: v for k, v in raw.items()
                                if k not in {"id", "firstName", "lastName", "email", "phone", "mobile"}
                            },
                        },
                    )
                count += 1
            except Exception:
                logger.error(
                    "[BookingSystem %d] Failed to sync customer external_id=%s:\n%s",
                    self.booking_system.id, external_id, traceback.format_exc(),
                )
        logger.info("[BookingSystem %d] Synced %d customers", self.booking_system.id, count)
        return count

    def sync_services(self) -> int:
        """Fetch and upsert all services. Returns count of synced records."""
        records = self.client.get_services()
        count = 0
        for raw in records:
            external_id = str(raw["id"])
            try:
                with transaction.atomic():
                    Service.objects.update_or_create(
                        booking_system=self.booking_system,
                        external_id=external_id,
                        defaults={
                            "name":             _str(raw.get("name")),
                            "duration_minutes": raw.get("duration") or 0,
                            "price":            _decimal(raw.get("price")),
                            "currency":         _str(raw.get("currency"), "USD"),
                            "extra_data": {
                                k: v for k, v in raw.items()
                                if k not in {"id", "name", "duration", "price", "currency"}
                            },
                        },
                    )
                count += 1
            except Exception:
                logger.error(
                    "[BookingSystem %d] Failed to sync service external_id=%s:\n%s",
                    self.booking_system.id, external_id, traceback.format_exc(),
                )
        logger.info("[BookingSystem %d] Synced %d services", self.booking_system.id, count)
        return count

    def sync_appointments(self) -> int:
        """
        Fetch and upsert all appointments.

        FK resolution: looks up Provider, Customer, Service by their
        external_id within this booking system. Skips the appointment
        (with a warning) if any FK cannot be found.
        """
        records = self.client.get_appointments()
        count = 0

        # Build lookup maps: external_id → local pk
        provider_map  = dict(
            Provider.objects.filter(booking_system=self.booking_system)
            .values_list("external_id", "id")
        )
        customer_map  = dict(
            Customer.objects.filter(booking_system=self.booking_system)
            .values_list("external_id", "id")
        )
        service_map   = dict(
            Service.objects.filter(booking_system=self.booking_system)
            .values_list("external_id", "id")
        )

        for raw in records:
            external_id  = str(raw["id"])
            provider_eid = str(raw.get("providerId", ""))
            customer_eid = str(raw.get("customerId", ""))
            service_eid  = str(raw.get("serviceId", ""))

            # Resolve FKs
            provider_pk = provider_map.get(provider_eid)
            customer_pk = customer_map.get(customer_eid)
            service_pk  = service_map.get(service_eid)

            if not provider_pk:
                logger.warning(
                    "[BookingSystem %d] Skipping appointment %s: provider external_id=%s not found",
                    self.booking_system.id, external_id, provider_eid,
                )
                continue
            if not customer_pk:
                logger.warning(
                    "[BookingSystem %d] Skipping appointment %s: customer external_id=%s not found",
                    self.booking_system.id, external_id, customer_eid,
                )
                continue
            if not service_pk:
                logger.warning(
                    "[BookingSystem %d] Skipping appointment %s: service external_id=%s not found",
                    self.booking_system.id, external_id, service_eid,
                )
                continue

            try:
                with transaction.atomic():
                    Appointment.objects.update_or_create(
                        booking_system=self.booking_system,
                        external_id=external_id,
                        defaults={
                            "provider_id":  provider_pk,
                            "customer_id":  customer_pk,
                            "service_id":   service_pk,
                            "start_time":   raw.get("start"),
                            "end_time":     raw.get("end"),
                            "status":       _str(raw.get("status"), "booked"),
                            "location":     _str(raw.get("location")),
                            "extra_data": {
                                k: v for k, v in raw.items()
                                if k not in {
                                    "id", "start", "end", "status", "location",
                                    "customerId", "providerId", "serviceId",
                                }
                            },
                        },
                    )
                count += 1
            except Exception:
                logger.error(
                    "[BookingSystem %d] Failed to sync appointment external_id=%s:\n%s",
                    self.booking_system.id, external_id, traceback.format_exc(),
                )

        logger.info("[BookingSystem %d] Synced %d appointments", self.booking_system.id, count)
        return count
