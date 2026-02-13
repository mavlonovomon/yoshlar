
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
import os
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-0dnjnv@%3ezlff)lp2m+$6w)aolg4$9@b3aoz_1!-$4z&2#iz1')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

raw_allowed_hosts = os.environ.get(
    'ALLOWED_HOSTS',
    '127.0.0.1,localhost,0.0.0.0,192.168.1.4'
)
ALLOWED_HOSTS = [host.strip() for host in raw_allowed_hosts.split(',') if host.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'core',
    'ishsiz_yoshlar',
    'otaliq',
    'migratsiya',
    'reyd',
    'beshtashabbus',
    'yoqlama',
    'profilaktika',
    'kredit_yo_naltirish',
    'intizom_jazo',
    'auth.apps.EimzoAuthConfig',
    'bilim_sinovi',
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

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ishsiz_yoshlar.context_processors.task_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'yoshlar.db',
    }
}

# User Model
AUTH_USER_MODEL = 'core.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'auth.backends.EimzoBackend',
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'uz-uz'  # Uzbek locale if available, or just generic
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# E-IMZO nonce TTL (seconds)
EIMZO_NONCE_TTL_SECONDS = 120
EIMZO_CA_BUNDLE_PATH = os.environ.get(
    'EIMZO_CA_BUNDLE_PATH',
    str(BASE_DIR / 'certs' / 'eimzo_ca_bundle.pem')
)

MUTOLAA_STATS_URL = os.environ.get(
    'MUTOLAA_STATS_URL',
    "https://api.mutolaa.com/api/v1/stats/NeighborhoodForStatistics/?offset=0&limit=47&parent__parent=8649&ordering&parent=8857"
)

USTOZ_AI_STATS_URL = os.environ.get(
    'USTOZ_AI_STATS_URL',
    "https://api.ustozaibot.uz/api/v1/statistics-cached/village-school?district=Xazorasp+tumani&region=Xorazm+viloyati"
)

UZCHESS_STATS_URL = os.environ.get(
    'UZCHESS_STATS_URL',
    "https://api.uzchesss.uz/api/statistics/count-by-neighborhood?page=1&region=Xorazm+viloyati&district=Xazorasp+tumani"
)

QIZLAR_STATS_URL = os.environ.get(
    'QIZLAR_STATS_URL',
    "https://api.qizlarakademiyasi.uz/api/statistics/count-by-neighborhood?page=1&region=Xorazm+viloyati&district=Xazorasp+tumani&sortBy=profiles"
)

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Auth URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
