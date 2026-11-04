"""
Django settings for gynae_oncology project.
Oncology Patient & MDT Database Migration from MS Access.
Cross-platform compatible: Windows 10/11 native & Ubuntu Linux.
"""

from pathlib import Path
import os
import sys

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Add apps folder to Python module lookup path
sys.path.insert(0, str(BASE_DIR / 'apps'))

# Load optional .env file
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-gynae-mdt-oncology-database-key-2026')
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Domain Applications
    'core.apps.CoreConfig',
    'patients.apps.PatientsConfig',
    'clinical.apps.ClinicalConfig',
    'investigations.apps.InvestigationsConfig',
    'radiotherapy.apps.RadiotherapyConfig',
    'systemic.apps.SystemicConfig',
    'followup.apps.FollowupConfig',
    'documents.apps.DocumentsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gynae_oncology.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.app_branding',
            ],
        },
    },
]

WSGI_APPLICATION = 'gynae_oncology.wsgi.application'

# Database Configuration (PostgreSQL primary with seamless SQLite development fallback)
DB_ENGINE = os.getenv('DB_ENGINE', '').lower()
DB_NAME = os.getenv('DB_NAME', os.getenv('POSTGRES_DB', 'gynae_oncology'))
DB_USER = os.getenv('DB_USER', os.getenv('POSTGRES_USER', 'postgres'))
DB_PASSWORD = os.getenv('DB_PASSWORD', os.getenv('POSTGRES_PASSWORD', 'postgres'))
DB_HOST = os.getenv('DB_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
DB_PORT = os.getenv('DB_PORT', os.getenv('POSTGRES_PORT', '5432'))

if DB_ENGINE == 'sqlite' or os.getenv('USE_SQLITE', 'false').lower() in ('true', '1', 'yes'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # Try connecting to PostgreSQL, with graceful fallback for local development if server not yet started
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images, SVG)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media Files (User uploads: documents, photos, scans, videos)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
PRIVATE_MEDIA_ROOT = BASE_DIR / 'media' / 'private'

# Authentication URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
