# This makes Celery load when Django starts (required for @shared_task to work)
from .celery import app as celery_app  # noqa: F401

__all__ = ("celery_app",)
