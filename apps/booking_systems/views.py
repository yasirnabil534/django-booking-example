from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from apps.core.pagination import EnvelopePagination
from .models import BookingSystem, Provider, Customer, Service, Appointment
from .serializers import (
    BookingSystemConnectSerializer,
    BookingSystemStatusSerializer,
    ProviderSerializer,
    CustomerSerializer,
    ServiceSerializer,
    AppointmentSerializer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_booking_system(pk):
    """Return BookingSystem or raise 404."""
    return get_object_or_404(BookingSystem, pk=pk)


class _BookingSystemSubListView(generics.ListAPIView):
    """
    Base class for all /{id}/resource/ list views.
    Subclasses just set `serializer_class` and `related_name`.
    """
    pagination_class = EnvelopePagination
    related_name: str = ""

    def get_queryset(self):
        bs = _get_booking_system(self.kwargs["pk"])
        return getattr(bs, self.related_name).all()


# ---------------------------------------------------------------------------
# POST /api/booking-systems/connect/
# ---------------------------------------------------------------------------

@extend_schema(
    summary="Register a new booking system",
    description="Connect to an external booking system (e.g. Easy!Appointments) by providing its URL and credentials.",
    request=BookingSystemConnectSerializer,
    responses={
        201: BookingSystemConnectSerializer,
        400: OpenApiTypes.OBJECT,
    },
    examples=[
        OpenApiExample(
            "Easy!Appointments (local)",
            summary="Local Easy!Appointments instance",
            description="Connect to a locally running Easy!Appointments Docker instance.",
            value={
                "name": "My Salon",
                "base_url": "http://localhost:8888",
                "username": "admin",
                "password": "admin123",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Success response",
            summary="201 Created",
            value={
                "data": {
                    "id": 1,
                    "name": "My Salon",
                    "base_url": "http://localhost:8888",
                    "is_active": True,
                    "created_at": "2026-03-15T17:35:20.357Z",
                },
                "errors": [],
                "meta": None,
            },
            response_only=True,
            status_codes=["201"],
        ),
        OpenApiExample(
            "Validation error",
            summary="400 Bad Request",
            value={
                "data": None,
                "errors": [{"message": "base_url: Enter a valid URL."}],
                "meta": None,
            },
            response_only=True,
            status_codes=["400"],
        ),
    ],
)
class BookingSystemConnectView(APIView):
    """Register a new booking system connection."""

    def post(self, request):
        serializer = BookingSystemConnectSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            return Response(
                {"data": BookingSystemConnectSerializer(instance).data, "errors": [], "meta": None},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"data": None, "errors": self._format_errors(serializer.errors), "meta": None},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @staticmethod
    def _format_errors(errors):
        messages = []
        for field, errs in errors.items():
            for err in errs:
                label = "" if field == "non_field_errors" else f"{field}: "
                messages.append({"message": f"{label}{err}"})
        return messages


# ---------------------------------------------------------------------------
# GET /api/booking-systems/{id}/status/
# ---------------------------------------------------------------------------

@extend_schema(
    summary="Get booking system status",
    description="Returns connection status, last sync time, and total record counts for each synced model.",
    responses={200: BookingSystemStatusSerializer},
    examples=[
        OpenApiExample(
            "Status response",
            summary="200 OK",
            value={
                "data": {
                    "id": 1,
                    "name": "My Salon",
                    "base_url": "http://localhost:8888",
                    "is_active": True,
                    "sync_status": "idle",
                    "last_synced_at": None,
                    "record_counts": {
                        "providers": 5,
                        "customers": 15,
                        "services": 12,
                        "appointments": 772,
                    },
                    "created_at": "2026-03-15T17:35:20.357Z",
                    "updated_at": "2026-03-15T17:35:20.357Z",
                },
                "errors": [],
                "meta": None,
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class BookingSystemStatusView(APIView):
    """Return connection status and record counts for a booking system."""

    def get(self, request, pk):
        bs = _get_booking_system(pk)
        serializer = BookingSystemStatusSerializer(bs)
        return Response({"data": serializer.data, "errors": [], "meta": None})


# ---------------------------------------------------------------------------
# GET /api/booking-systems/{id}/providers/
# ---------------------------------------------------------------------------

@extend_schema(
    summary="List providers",
    description="List all synced providers (staff members) for a booking system. Supports search by name and pagination.",
    parameters=[
        OpenApiParameter("search", OpenApiTypes.STR, description="Filter by first or last name (case-insensitive)"),
    ],
    responses={200: ProviderSerializer(many=True)},
    examples=[
        OpenApiExample(
            "Providers list",
            summary="200 OK",
            value={
                "data": [
                    {
                        "id": 1,
                        "booking_system": 1,
                        "first_name": "Sarah",
                        "last_name": "Johnson",
                        "email": "sarah@testsalon.com",
                        "phone": "+1-555-0101",
                        "external_id": "4",
                        "extra_data": {},
                        "created_at": "2026-03-15T17:35:20.357Z",
                        "updated_at": "2026-03-15T17:35:20.357Z",
                    },
                ],
                "errors": [],
                "meta": {"page": 1, "total_pages": 1, "total_count": 5},
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class ProviderListView(_BookingSystemSubListView):
    """List providers for a booking system (paginated, search by name)."""
    serializer_class = ProviderSerializer
    related_name = "providers"

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )
        return qs.order_by("last_name", "first_name")


# ---------------------------------------------------------------------------
# GET /api/booking-systems/{id}/customers/
# ---------------------------------------------------------------------------

@extend_schema(
    summary="List customers",
    description="List all synced customers for a booking system. Supports search by name and pagination.",
    parameters=[
        OpenApiParameter("search", OpenApiTypes.STR, description="Filter by first or last name (case-insensitive)"),
    ],
    responses={200: CustomerSerializer(many=True)},
    examples=[
        OpenApiExample(
            "Customers list",
            summary="200 OK",
            value={
                "data": [
                    {
                        "id": 1,
                        "booking_system": 1,
                        "first_name": "Alice",
                        "last_name": "Brown",
                        "email": "alice@email.com",
                        "phone": "+1-555-1001",
                        "external_id": "9",
                        "extra_data": {},
                        "created_at": "2026-03-15T17:35:20.357Z",
                        "updated_at": "2026-03-15T17:35:20.357Z",
                    },
                ],
                "errors": [],
                "meta": {"page": 1, "total_pages": 1, "total_count": 15},
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class CustomerListView(_BookingSystemSubListView):
    """List customers for a booking system (paginated, search by name)."""
    serializer_class = CustomerSerializer
    related_name = "customers"

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )
        return qs.order_by("last_name", "first_name")


# ---------------------------------------------------------------------------
# GET /api/booking-systems/{id}/services/
# ---------------------------------------------------------------------------

@extend_schema(
    summary="List services",
    description="List all synced services offered by the booking system, paginated.",
    responses={200: ServiceSerializer(many=True)},
    examples=[
        OpenApiExample(
            "Services list",
            summary="200 OK",
            value={
                "data": [
                    {
                        "id": 1,
                        "booking_system": 1,
                        "name": "Men's Haircut",
                        "duration_minutes": 30,
                        "price": "35.00",
                        "currency": "USD",
                        "external_id": "2",
                        "extra_data": {},
                        "created_at": "2026-03-15T17:35:20.357Z",
                        "updated_at": "2026-03-15T17:35:20.357Z",
                    },
                ],
                "errors": [],
                "meta": {"page": 1, "total_pages": 1, "total_count": 12},
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class ServiceListView(_BookingSystemSubListView):
    """List services for a booking system (paginated)."""
    serializer_class = ServiceSerializer
    related_name = "services"

    def get_queryset(self):
        return super().get_queryset().order_by("name")


# ---------------------------------------------------------------------------
# GET /api/booking-systems/{id}/appointments/
# ---------------------------------------------------------------------------

@extend_schema(
    summary="List appointments",
    description="List all synced appointments. Filter by date range using `start_date` and `end_date` (YYYY-MM-DD).",
    parameters=[
        OpenApiParameter("start_date", OpenApiTypes.DATE, description="Filter appointments starting on or after this date (YYYY-MM-DD)"),
        OpenApiParameter("end_date",   OpenApiTypes.DATE, description="Filter appointments starting on or before this date (YYYY-MM-DD)"),
    ],
    responses={200: AppointmentSerializer(many=True)},
    examples=[
        OpenApiExample(
            "Appointments list",
            summary="200 OK",
            value={
                "data": [
                    {
                        "id": 1,
                        "booking_system": 1,
                        "provider": 1,
                        "customer": 3,
                        "service": 2,
                        "start_time": "2026-01-05T09:00:00Z",
                        "end_time": "2026-01-05T09:30:00Z",
                        "status": "booked",
                        "location": "Test Salon - Main Branch",
                        "external_id": "101",
                        "extra_data": {},
                        "created_at": "2026-03-15T17:35:20.357Z",
                        "updated_at": "2026-03-15T17:35:20.357Z",
                    },
                ],
                "errors": [],
                "meta": {"page": 1, "total_pages": 39, "total_count": 772},
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class AppointmentListView(_BookingSystemSubListView):
    """
    List appointments for a booking system.
    Optional query params: start_date (YYYY-MM-DD), end_date (YYYY-MM-DD)
    """
    serializer_class = AppointmentSerializer
    related_name = "appointments"

    def get_queryset(self):
        qs = super().get_queryset()
        start_date = self.request.query_params.get("start_date")
        end_date   = self.request.query_params.get("end_date")
        if start_date:
            qs = qs.filter(start_time__date__gte=start_date)
        if end_date:
            qs = qs.filter(start_time__date__lte=end_date)
        return qs.select_related("provider", "customer", "service").order_by("start_time")


# ---------------------------------------------------------------------------
# POST /api/booking-systems/{id}/sync/
# ---------------------------------------------------------------------------

@extend_schema(
    summary="Trigger a full sync",
    description=(
        "Dispatches a Celery task to sync all data from the external booking system "
        "(providers → customers → services → appointments). Returns the Celery task ID."
    ),
    responses={202: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Sync triggered",
            summary="202 Accepted",
            value={"data": {"task_id": "d3f1a2b4-1234-5678-abcd-ef1234567890"}, "errors": [], "meta": None},
            response_only=True,
            status_codes=["202"],
        ),
    ],
)
class SyncTriggerView(APIView):
    """Trigger a full background sync for a booking system."""

    def post(self, request, pk):
        from .tasks import sync_booking_system_task
        bs = _get_booking_system(pk)
        result = sync_booking_system_task.delay(bs.id)
        return Response(
            {"data": {"task_id": result.id}, "errors": [], "meta": None},
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------------------------------------------------------------------
# GET /api/booking-systems/{id}/sync/status/
# ---------------------------------------------------------------------------

@extend_schema(
    summary="Get sync status",
    description="Returns the current sync status, last successful sync time, and any last error message.",
    responses={200: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            "Sync status",
            summary="200 OK — idle after successful sync",
            value={
                "data": {
                    "sync_status": "idle",
                    "last_synced_at": "2026-03-16T10:00:00Z",
                    "last_sync_error": "",
                },
                "errors": [],
                "meta": None,
            },
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "Sync failed",
            summary="200 OK — last sync failed",
            value={
                "data": {
                    "sync_status": "failed",
                    "last_synced_at": "2026-03-15T10:00:00Z",
                    "last_sync_error": "AuthenticationError: Invalid credentials",
                },
                "errors": [],
                "meta": None,
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class SyncStatusView(APIView):
    """Return sync status, last sync time, and last error for a booking system."""

    def get(self, request, pk):
        bs = _get_booking_system(pk)
        return Response({
            "data": {
                "sync_status":    bs.sync_status,
                "last_synced_at": bs.last_synced_at,
                "last_sync_error": bs.last_sync_error,
            },
            "errors": [],
            "meta": None,
        })
