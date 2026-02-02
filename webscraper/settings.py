import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR.parent / '.env')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# --- THIS IS ONE OF YOUR 3 KEYS ---
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "your-django-secret-key-here")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost",".ngrok.io",'kaleigh-unsophistic-applicatively.ngrok-free.dev']

CSRF_TRUSTED_ORIGINS = [
    'https://kaleigh-unsophistic-applicatively.ngrok-free.dev'
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django_extensions',
    'django.contrib.staticfiles',
    'core',  
    'archive_etl',
    'chatbot'
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

ROOT_URLCONF = 'webscraper.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Added top-level templates dir
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

WSGI_APPLICATION = 'webscraper.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,  # CRITICAL: Fix for "database is locked" errors
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Amman'


USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
# Point to the source static directories for each app
STATICFILES_DIRS = [
    BASE_DIR / 'core' / 'static',
    BASE_DIR / 'templates',  # if you have static files in templates dir
]
# Used for collectstatic in production
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Auth Redirects ---
LOGIN_REDIRECT_URL = 'home' 

# The page users are sent to if they try to access a protected view
LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = 'home'


# --- API KEYS & PROJECT SETTINGS ---
# This is where you put your 3 secret keys!
# -------------------------------------

# Get values from .env
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
DEBUG = os.getenv('DEBUG', 'False') == '1'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

# Celery Configuration
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')

# Gemini API
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
CHATBOT_API_KEY = os.getenv("CHATBOT_API_KEY")
HF_API_TOKEN = os.getenv('HF_API_TOKEN')
HF_SUMMARY_MODEL = os.getenv('HF_SUMMARY_MODEL')



# Scraper settings
SAFE_SCRAPING_ENFORCED = True

SCRAPER_SITE_PROFILES = {}
SCRAPER_SITE_PROFILES_FILE = str(BASE_DIR / 'site_profiles.json')