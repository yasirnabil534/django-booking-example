from django.db import models


class TimestampedModel(models.Model):
    """Abstract base that adds created_at / updated_at to every model."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BookingSystem(TimestampedModel):
    """Represents a connected external scheduling system (e.g. Easy!Appointments)."""

    class SyncStatus(models.TextChoices):
        IDLE    = "idle",    "Idle"
        RUNNING = "running", "Running"
        FAILED  = "failed",  "Failed"

    name        = models.CharField(max_length=255)
    base_url    = models.URLField(max_length=500)
    # Stores {"username": "...", "password": "..."} — never expose in API responses
    credentials = models.JSONField(default=dict)
    is_active   = models.BooleanField(default=True)
    sync_status = models.CharField(
        max_length=10,
        choices=SyncStatus.choices,
        default=SyncStatus.IDLE,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "booking_system"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.base_url})"


class Provider(TimestampedModel):
    """Staff member / service provider synced from an external booking system."""

    booking_system = models.ForeignKey(
        BookingSystem, on_delete=models.CASCADE, related_name="providers"
    )
    first_name  = models.CharField(max_length=100)
    last_name   = models.CharField(max_length=100)
    email       = models.EmailField(max_length=255)
    phone       = models.CharField(max_length=50, blank=True)
    external_id = models.CharField(max_length=255)
    extra_data  = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "provider"
        unique_together = [("booking_system", "external_id")]
        indexes = [
            models.Index(fields=["booking_system", "last_name", "first_name"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} (ext:{self.external_id})"


class Customer(TimestampedModel):
    """Customer synced from an external booking system."""

    booking_system = models.ForeignKey(
        BookingSystem, on_delete=models.CASCADE, related_name="customers"
    )
    first_name  = models.CharField(max_length=100)
    last_name   = models.CharField(max_length=100)
    email       = models.EmailField(max_length=255)
    phone       = models.CharField(max_length=50, blank=True)
    external_id = models.CharField(max_length=255)
    extra_data  = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "customer"
        unique_together = [("booking_system", "external_id")]
        indexes = [
            models.Index(fields=["booking_system", "last_name", "first_name"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} (ext:{self.external_id})"


class Service(TimestampedModel):
    """Service offered by providers on an external booking system."""

    booking_system   = models.ForeignKey(
        BookingSystem, on_delete=models.CASCADE, related_name="services"
    )
    name             = models.CharField(max_length=255)
    duration_minutes = models.PositiveIntegerField()
    price            = models.DecimalField(max_digits=10, decimal_places=2)
    currency         = models.CharField(max_length=10, default="USD")
    external_id      = models.CharField(max_length=255)
    extra_data       = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "service"
        unique_together = [("booking_system", "external_id")]
        indexes = [
            models.Index(fields=["booking_system", "name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.duration_minutes}min @ {self.price} {self.currency})"


class Appointment(TimestampedModel):
    """Booked appointment synced from an external booking system."""

    class Status(models.TextChoices):
        BOOKED    = "booked",    "Booked"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW   = "no_show",   "No Show"

    booking_system = models.ForeignKey(
        BookingSystem, on_delete=models.CASCADE, related_name="appointments"
    )
    provider = models.ForeignKey(
        Provider, on_delete=models.SET_NULL, null=True, related_name="appointments"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, related_name="appointments"
    )
    service = models.ForeignKey(
        Service, on_delete=models.SET_NULL, null=True, related_name="appointments"
    )
    start_time  = models.DateTimeField()
    end_time    = models.DateTimeField()
    status      = models.CharField(
        max_length=10, choices=Status.choices, default=Status.BOOKED
    )
    location    = models.CharField(max_length=500, blank=True)
    external_id = models.CharField(max_length=255)
    extra_data  = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "appointment"
        unique_together = [("booking_system", "external_id")]
        indexes = [
            models.Index(fields=["booking_system", "start_time"]),
            models.Index(fields=["booking_system", "status"]),
            models.Index(fields=["start_time", "end_time"]),
        ]
        ordering = ["start_time"]

    def __str__(self):
        return f"Appt {self.external_id}: {self.start_time} ({self.status})"
