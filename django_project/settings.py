from pathlib import Path
import os, pymysql, dj_database_url

pymysql.install_as_MySQLdb()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
BASE_URL = os.environ['BASE_URL']

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'shshshsah9197191299721297hssjhjsh')

FIELD_ENCRYPTION_KEY = os.environ['FIELD_ENCRYPTION_KEY'].encode()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = []

if os.environ.get('ALLOWED_HOSTS'):
    ALLOWED_HOSTS.extend(os.environ.get('ALLOWED_HOSTS').split(','))

# Application definition

INSTALLED_APPS = [
    'main',
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pwa',
    'mathfilters',
    'encrypted_model_fields',
    'corsheaders',
    'cacheops',
    # 'rangefilter',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'main.middlewares.logger.ErrorLogger',
]

ROOT_URLCONF = 'django_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'main.context_processors.main'
            ],
        },
    },
]

if DEBUG:
    TEMPLATES[0]['OPTIONS']['context_processors'].append('main.context_processors.debug')
else:
    TEMPLATES[0]['OPTIONS']['context_processors'].append('main.context_processors.production')


WSGI_APPLICATION = 'django_project.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if os.environ.get('DATABASE_URL'):
    DATABASES['default'] = {
        # 'DISABLE_SERVER_SIDE_CURSORS': True,
        **dj_database_url.parse(os.environ.get('DATABASE_URL'))
    }

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'id-ID'

from zoneinfo import ZoneInfo

TIME_ZONE = 'Asia/Jakarta'
TIME_ZONE_OBJ = ZoneInfo(TIME_ZONE)


USE_I18N = True

USE_L10N = True

USE_TZ = True

# Whitenoise

USE_WHITENOISE = os.environ.get('USE_WHITENOISE', 'True') == 'True'

if USE_WHITENOISE:
    MIDDLEWARE.insert(0, 'whitenoise.middleware.WhiteNoiseMiddleware')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.environ.get('STATIC_ROOT', BASE_DIR / 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'

PWA_APP_NAME = 'Malik Wallet'
PWA_APP_DESCRIPTION = 'Dompet digital untuk kebutuhan ponpes'
PWA_APP_ORIENTATION = 'horizontal'
PWA_APP_ICONS = [
    {
        'src': '/static/images/logo.jpg',
        'sizes': '160x160'
    }
]
PWA_APP_SPLASH_SCREEN = [
    {
        'src': '/static/images/splash.jpg',
        'media': '(device-width: 320px) and (device-height: 568px) and (-webkit-device-pixel-ratio: 2)'
    }
]

PWA_SERVICE_WORKER_PATH = os.path.join(BASE_DIR, 'main', 'static', 'js', 'serviceworker.js')

CORS_ALLOWED_ORIGINS = os.environ['CORS_ALLOWED_ORIGINS'].split(',')

PWA_APP_LANG = 'id-ID'

TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']

DISABLE_SIGNALS = os.environ.get('DISABLE_SIGNALS', 'False') == 'True'

SANDBOX = os.environ.get('SANDBOX', 'True') == 'True'

DIGIFLAZZ_USERNAME = os.environ['DIGIFLAZZ_USERNAME']
DIGIFLAZZ_API_KEY = os.environ['DIGIFLAZZ_API_KEY']
DIGIFLAZZ_SECRET_KEY = os.environ['DIGIFLAZZ_SECRET_KEY']

BEAMS_PUSHER_INSTANCE_ID = os.environ['BEAMS_PUSHER_INSTANCE_ID']
BEAMS_PUSHER_SECRET_KEY = os.environ['BEAMS_PUSHER_SECRET_KEY']

CACHEOPS_REDIS = os.environ['REDIS_URL']
CACHEOPS_DEFAULTS = {
    'timeout': 10 * 60
}

CACHEOPS = {
    'main.*':  {'ops': 'all'},
    'auth.user':  {'ops': 'all'},
    'auth.group':  {'ops': 'all'},
}

PUBLIC_CONTEXT = {
    'TITLE': 'Malik Wallet',
    'BEAMS_PUSHER_INSTANCE_ID': BEAMS_PUSHER_INSTANCE_ID,
    'BASE_URL': BASE_URL
}

RECIPIENT_HTML = os.environ.get('RECIPIENT_HTML', '')