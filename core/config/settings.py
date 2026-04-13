"""
Django settings for GroupBuy Bot Core API
"""
import os
from pathlib import Path
from urllib.parse import urlparse

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
# Set DEBUG=False and ALLOWED_HOSTS=your-domain.com in production via environment variables.
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

_default_hosts = '*' if DEBUG else 'localhost,127.0.0.1'
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', _default_hosts).split(',') if h.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    # Local apps
    'users',
    'procurements',
    'chat',
    'payments',
    'admin_api',
    'ml',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR.parent / 'frontend' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/groupbuy')
db_url = urlparse(DATABASE_URL)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': db_url.path[1:],
        'USER': db_url.username,
        'PASSWORD': db_url.password,
        'HOST': db_url.hostname,
        'PORT': db_url.port or 5432,
    }
}

# Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Caches
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Only include the legacy frontend/static dir when it actually exists on disk
# (it is absent inside the Django Docker container, which only copies ./core/).
_legacy_static = BASE_DIR.parent / 'frontend' / 'static'
STATICFILES_DIRS = [_legacy_static] if _legacy_static.is_dir() else []

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# CORS — When CORS_ALLOW_ALL_ORIGINS is explicitly set to True in the environment,
# all origins are permitted regardless of CORS_ALLOWED_ORIGINS.  When
# CORS_ALLOWED_ORIGINS is set (and CORS_ALLOW_ALL_ORIGINS is not True), only
# those origins are allowed.  Otherwise all origins are permitted by default.
_cors_allow_all_env = os.getenv('CORS_ALLOW_ALL_ORIGINS', '').lower()
_cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS', '')
if _cors_allow_all_env == 'true':
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_env.split(',') if o.strip()] if _cors_origins_env else []
elif _cors_origins_env:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_env.split(',') if o.strip()]
else:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_CREDENTIALS = True

# Session / CSRF cookie settings for cross-origin admin panel
CSRF_COOKIE_HTTPONLY = False  # Allow JS to read the CSRF token
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]

# DRF Spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'GroupBuy Bot API',
    'DESCRIPTION': 'API for GroupBuy Bot - a multi-platform group purchasing bot',
    'VERSION': '1.0.0',
}

# Tochka Bank (Cyclops) Payment Integration
TOCHKA_API_URL = os.getenv('TOCHKA_API_URL', 'https://pre.tochka.com/api/v1/cyclops')
TOCHKA_NOMINAL_ACCOUNT = os.getenv('TOCHKA_NOMINAL_ACCOUNT', '')
TOCHKA_PLATFORM_ID = os.getenv('TOCHKA_PLATFORM_ID', '')
TOCHKA_PRIVATE_KEY_PATH = os.getenv('TOCHKA_PRIVATE_KEY_PATH', '')
TOCHKA_PUBLIC_KEY_PATH = os.getenv('TOCHKA_PUBLIC_KEY_PATH', '')

# Payment return URL (after payment completion)
PAYMENT_RETURN_URL = os.getenv('PAYMENT_RETURN_URL', '')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
}
