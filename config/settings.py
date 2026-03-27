
from pathlib import Path
import os
from urllib.parse import parse_qs, unquote, urlparse


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
_load_env_file(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-0dnjnv@%3ezlff)lp2m+$6w)aolg4$9@b3aoz_1!-$4z&2#iz1')

# SECURITY WARNING: don't run with debug turned on in production!
def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    return default


def _env_list(name, default=''):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


DEBUG = _env_bool('DJANGO_DEBUG', _env_bool('DEBUG', True))

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
    'hisobot',
    'sorovnoma',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.IdleSessionMiddleware',
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

def _database_config_from_url(database_url: str) -> dict:
    parsed = urlparse(database_url)
    scheme = (parsed.scheme or '').lower()

    if scheme in {'sqlite', 'sqlite3'}:
        raw_path = unquote(parsed.path or '')
        if raw_path in {'', '/', '/:memory:'}:
            name = ':memory:'
        else:
            if parsed.netloc:
                name = Path(f"//{parsed.netloc}{raw_path}")
            elif raw_path.startswith(('/', '\\')) or (len(raw_path) >= 2 and raw_path[1] == ':'):
                name = Path(raw_path)
            else:
                name = BASE_DIR / raw_path
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(name),
        }

    if scheme in {'postgres', 'postgresql', 'postgresql+psycopg', 'postgresql_psycopg'}:
        query = parse_qs(parsed.query)
        sslmode = query.get('sslmode', [None])[0]
        config = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote(parsed.path.lstrip('/')),
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or '',
            'PORT': parsed.port or '',
        }
        if sslmode:
            config['OPTIONS'] = {'sslmode': sslmode}
        return config

    raise ValueError(f"Qo'llab-quvvatlanmagan DATABASE_URL sxemasi: {scheme}")


def _build_database_config() -> dict:
    database_url = (
        os.environ.get('DATABASE_URL')
        or os.environ.get('DB_URL')
        or ''
    ).strip()
    if database_url:
        return _database_config_from_url(database_url)

    sqlite_path = Path(
        os.environ.get('SQLITE_PATH')
        or os.environ.get('DB_PATH')
        or (BASE_DIR / 'yoshlar.db')
    )
    return {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': sqlite_path,
    }


DATABASES = {
    'default': _build_database_config(),
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
USE_TZ = True
USE_X_FORWARDED_HOST = _env_bool('USE_X_FORWARDED_HOST', True)
SECURE_PROXY_SSL_HEADER = (
    'HTTP_X_FORWARDED_PROTO',
    'https',
) if _env_bool('SECURE_PROXY_SSL_HEADER', True) else None
CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS')
SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = _env_bool('CSRF_COOKIE_SECURE', not DEBUG)
SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', False)
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '0') or 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = _env_bool('SECURE_HSTS_PRELOAD', False)
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

REPORT_AI_MODEL = os.environ.get('REPORT_AI_MODEL', 'gpt-4.1-mini')
REPORT_AI_BASE_URL = os.environ.get('REPORT_AI_BASE_URL', os.environ.get('OPENAI_BASE_URL', 'http://127.0.0.1:8045/v1'))
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'sk-edbf9aa2b8314de280144423658a15bd')
REPORT_FONT_PATH = os.environ.get('REPORT_FONT_PATH', '')
REPORT_FONT_BOLD_PATH = os.environ.get('REPORT_FONT_BOLD_PATH', '')

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = Path(os.environ.get('STATIC_ROOT', str(BASE_DIR / 'staticfiles')))
STATICFILES_USE_MANIFEST = _env_bool('STATICFILES_USE_MANIFEST', not DEBUG)

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
            if STATICFILES_USE_MANIFEST
            else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}
# Backward compatibility for older Django versions that still use STATICFILES_STORAGE.
STATICFILES_STORAGE = STORAGES['staticfiles']['BACKEND']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', str(BASE_DIR / 'media')))

# Auth URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Session inactivity timeout (seconds)
SESSION_COOKIE_AGE = int(os.environ.get('SESSION_COOKIE_AGE', '1800'))
SESSION_IDLE_TIMEOUT = int(os.environ.get('SESSION_IDLE_TIMEOUT', str(SESSION_COOKIE_AGE)))
SESSION_SAVE_EVERY_REQUEST = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
