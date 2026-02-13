import os
import django
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import User
from django.contrib.auth import get_user_model

User = get_user_model()

if not User.objects.filter(username='admin').exists():
    user = User.objects.create_superuser(
        'admin', 
        'admin@example.com', 
        os.environ.get('ADMIN_PASSWORD', 'admin123'),
        full_name='Super Admin'
    )
    user.role = 'SUPER_ADMIN'
    user.save()
    logger.info("✓ Superuser created successfully")
else:
    logger.info("✓ Superuser already exists")
