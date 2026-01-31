from .settings import *
import os

# SECURITY
DEBUG = False
ALLOWED_HOSTS = ['*']  # Railway will set the correct hostname
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# DATABASE - Railway PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB'),
        'USER': os.environ.get('POSTGRES_USER'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
        'HOST': os.environ.get('POSTGRES_HOST'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

# STATIC FILES
STATIC_URL = '/static/'
STATIC_ROOT = '/staticfiles/'

# MEDIA FILES
MEDIA_URL = '/media/'
MEDIA_ROOT = '/mediafiles/'

# PAYSTACK CONFIGURATION
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', 'sk_live_your_live_secret_key_here')
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', 'pk_live_your_live_public_key_here')
PAYSTACK_CALLBACK_URL = f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'your-app.railway.app')}/paystack/callback/"

# CORS HEADERS (if needed)
CORS_ALLOWED_ORIGINS = [
    "https://" + os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'your-app.railway.app'),
]

# SECURITY SETTINGS
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True