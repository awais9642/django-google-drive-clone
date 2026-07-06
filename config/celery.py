import os
from celery import Celery

# Tell Celery which Django settings module to use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('drive_clone')

# Pull Celery config from Django settings (any key starting with CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
# Celery looks for a tasks.py file in each app
app.autodiscover_tasks()