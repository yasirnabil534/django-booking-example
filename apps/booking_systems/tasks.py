"""
Celery tasks for the booking systems sync pipeline.

Tasks
-----
- sync_booking_system_task  : full sync (providers → customers → services → appointments)
- sync_providers_task        : sync only providers
- sync_appointments_task     : sync only appointments
- sync_all_active_booking_systems : Beat-triggered task — fans out to all active systems

Beat schedule
-------------
sync_all_active_booking_systems runs every 6 hours for all is_active=True systems.
"""

import logging
import traceback

from celery import shared_task
from celery.schedules import crontab
from django.utils import timezone

from config.celery import app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Beat schedule (registered on the Celery app object)
# ---------------------------------------------------------------------------

app.conf.beat_schedule = {
    "sync-all-active-booking-systems-every-6h": {
        "task": "apps.booking_systems.tasks.sync_all_active_booking_systems",
        "schedule": crontab(minute=0, hour="*/6"),
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_booking_system(booking_system_id: int):
    """Import here to avoid circular imports at module level."""
    from .models import BookingSystem
    return BookingSystem.objects.get(pk=booking_system_id)


def _set_syncing(bs):
    from .models import BookingSystem
    bs.sync_status = BookingSystem.SyncStatus.RUNNING
    bs.last_sync_error = ""
    bs.save(update_fields=["sync_status", "last_sync_error"])


def _set_success(bs):
    from .models import BookingSystem
    bs.sync_status = BookingSystem.SyncStatus.IDLE
    bs.last_synced_at = timezone.now()
    bs.last_sync_error = ""
    bs.save(update_fields=["sync_status", "last_synced_at", "last_sync_error"])


def _set_failed(bs, error: str):
    from .models import BookingSystem
    bs.sync_status = BookingSystem.SyncStatus.FAILED
    bs.last_sync_error = error[:2000]  # cap at 2000 chars
    bs.save(update_fields=["sync_status", "last_sync_error"])


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@shared_task(name="apps.booking_systems.tasks.sync_booking_system_task", bind=True)
def sync_booking_system_task(self, booking_system_id: int) -> dict:
    """
    Full sync for a single booking system.
    Runs in order: providers → customers → services → appointments.
    Updates last_synced_at only if all steps succeed.
    On error: sets sync_status='failed', stores error message, re-raises.
    """
    from .sync import DataSyncHandler

    logger.info("sync_booking_system_task started for BookingSystem id=%d", booking_system_id)
    bs = _get_booking_system(booking_system_id)
    _set_syncing(bs)

    try:
        handler = DataSyncHandler(bs)
        summary = handler.sync_all()
        _set_success(bs)
        logger.info("sync_booking_system_task complete for id=%d: %s", booking_system_id, summary)
        return summary
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        logger.error(
            "sync_booking_system_task FAILED for BookingSystem id=%d: %s",
            booking_system_id, error_msg,
        )
        _set_failed(bs, error_msg)
        raise  # let Celery mark the task as failed


@shared_task(name="apps.booking_systems.tasks.sync_providers_task", bind=True)
def sync_providers_task(self, booking_system_id: int) -> int:
    """Sync only providers for a booking system."""
    from .sync import DataSyncHandler

    logger.info("sync_providers_task started for BookingSystem id=%d", booking_system_id)
    bs = _get_booking_system(booking_system_id)

    try:
        count = DataSyncHandler(bs).sync_providers()
        logger.info("sync_providers_task complete: %d records", count)
        return count
    except Exception as exc:
        logger.error("sync_providers_task FAILED for id=%d: %s", booking_system_id, exc)
        raise


@shared_task(name="apps.booking_systems.tasks.sync_appointments_task", bind=True)
def sync_appointments_task(self, booking_system_id: int) -> int:
    """Sync only appointments for a booking system."""
    from .sync import DataSyncHandler

    logger.info("sync_appointments_task started for BookingSystem id=%d", booking_system_id)
    bs = _get_booking_system(booking_system_id)

    try:
        count = DataSyncHandler(bs).sync_appointments()
        logger.info("sync_appointments_task complete: %d records", count)
        return count
    except Exception as exc:
        logger.error("sync_appointments_task FAILED for id=%d: %s", booking_system_id, exc)
        raise


@shared_task(name="apps.booking_systems.tasks.sync_all_active_booking_systems")
def sync_all_active_booking_systems() -> dict:
    """
    Beat-triggered task: fan out sync_booking_system_task for every active system.
    Runs every 6 hours via the beat_schedule defined above.
    """
    from .models import BookingSystem

    active_ids = list(
        BookingSystem.objects.filter(is_active=True).values_list("id", flat=True)
    )
    logger.info("Beat: syncing %d active booking systems: %s", len(active_ids), active_ids)

    task_ids = {}
    for bs_id in active_ids:
        result = sync_booking_system_task.delay(bs_id)
        task_ids[bs_id] = result.id

    return task_ids
