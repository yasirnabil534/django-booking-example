from rest_framework import serializers
from .models import BookingSystem, Provider, Customer, Service, Appointment


# ---------------------------------------------------------------------------
# BookingSystem
# ---------------------------------------------------------------------------

class BookingSystemConnectSerializer(serializers.ModelSerializer):
    """Accepts name + base_url + username + password; stores creds as JSON."""
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = BookingSystem
        fields = ["id", "name", "base_url", "username", "password", "is_active", "created_at"]
        read_only_fields = ["id", "is_active", "created_at"]

    def create(self, validated_data):
        username = validated_data.pop("username")
        password = validated_data.pop("password")
        validated_data["credentials"] = {"username": username, "password": password}
        return super().create(validated_data)


class BookingSystemStatusSerializer(serializers.ModelSerializer):
    """Read-only status view — includes record counts per related model."""
    record_counts = serializers.SerializerMethodField()

    class Meta:
        model = BookingSystem
        fields = [
            "id", "name", "base_url", "is_active",
            "sync_status", "last_synced_at", "record_counts",
            "created_at", "updated_at",
        ]

    def get_record_counts(self, obj):
        return {
            "providers":    obj.providers.count(),
            "customers":    obj.customers.count(),
            "services":     obj.services.count(),
            "appointments": obj.appointments.count(),
        }


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = [
            "id", "booking_system", "first_name", "last_name",
            "email", "phone", "external_id", "extra_data",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id", "booking_system", "first_name", "last_name",
            "email", "phone", "external_id", "extra_data",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = [
            "id", "booking_system", "name", "duration_minutes",
            "price", "currency", "external_id", "extra_data",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Appointment
# ---------------------------------------------------------------------------

class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "id", "booking_system", "provider", "customer", "service",
            "start_time", "end_time", "status", "location",
            "external_id", "extra_data", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
