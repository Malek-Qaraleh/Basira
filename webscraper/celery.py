# In webscraper/celery.py

import os
import platform
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webscraper.settings')

app = Celery('webscraper')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps
app.autodiscover_tasks()

# Windows-specific configuration to avoid multiprocessing issues
if platform.system() == 'Windows':
    app.conf.update(
        worker_pool='solo',  # Use solo pool instead of prefork on Windows
    )