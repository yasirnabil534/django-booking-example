"""
Celery application for the booking sync project.

This module is imported by manage.py and wsgi.py so Celery is ready
when Django starts. Tasks are auto-discovered in all INSTALLED_APPS.
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("booking_sync")

# Pull all celery config from Django settings (CELERY_* keys)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks.py in every installed app
app.autodiscover_tasks()
