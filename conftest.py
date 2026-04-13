"""
Pytest configuration for running tests with SQLite (no PostgreSQL needed).
"""
import os
import sys

# Add core and bot directories to path so their modules can be imported directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

# Try to set up Django if available
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    # Must set before Django is imported so settings.py doesn't fail on DB URL parsing
    os.environ['DATABASE_URL'] = 'sqlite:///test.db'

    import django  # noqa: F401 - checked for availability below

    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False


def pytest_configure(config):
    """Override Django settings for tests."""
    if not DJANGO_AVAILABLE:
        return

    import django
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            ROOT_URLCONF='conftest_urls',
            ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            CACHES={
                'default': {
                    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.contenttypes',
                'django.contrib.auth',
                'django.contrib.sessions',
                'rest_framework',
                'corsheaders',
                'users',
                'procurements',
                'chat',
                'payments',
                'admin_api',
                'ml',
            ],
            MIDDLEWARE=[
                'django.contrib.sessions.middleware.SessionMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
            ],
            SESSION_ENGINE='django.contrib.sessions.backends.db',
            REST_FRAMEWORK={
                'DEFAULT_AUTHENTICATION_CLASSES': [
                    'rest_framework.authentication.SessionAuthentication',
                ],
                'DEFAULT_PERMISSION_CLASSES': [
                    'rest_framework.permissions.AllowAny',
                ],
                'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
                'PAGE_SIZE': 20,
            },
            DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
            USE_TZ=True,
            TIME_ZONE='Europe/Moscow',
            SECRET_KEY='test-secret-key-for-pytest',
        )
        django.setup()
        # Run migrations to create tables (pytest-django handles setup_test_environment)
        from django.core.management import call_command
        call_command('migrate', '--run-syncdb', verbosity=0)
    else:
        settings.DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        }
        settings.CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            }
        }
        from django.core.management import call_command
        call_command('migrate', '--run-syncdb', verbosity=0)
