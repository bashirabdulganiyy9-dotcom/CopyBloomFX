# pyright: reportMissingImports=false
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crypto_platform.railway_settings')
application = get_wsgi_application()
