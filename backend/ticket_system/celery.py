"""Celery application.

With REDIS_URL set, tasks go through Redis to the `worker` container and
`beat` runs the periodic SLA escalation. Without Redis (local runs, tests),
tasks execute inline (CELERY_TASK_ALWAYS_EAGER), so nothing extra is needed
to run the app.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ticket_system.settings")

app = Celery("nexusdesk")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
