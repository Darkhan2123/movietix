import os
from pathlib import Path
import dj_database_url

# Load environment variables from .env file if available
from .env_loader import load_env_vars
# Store the return value which will contain the loaded environment variables
env_vars = load_env_vars()
print(f"Environment loading complete. Variables detected: {len(env_vars)}")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Use environment variable, with fallback for development only
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-&gu_y1ldtunyk0(z^d=6q5==33og-3-pyr&br(prt7gx52o2y*')

# SECURITY WARNING: don't run with debug turned on in production!
# Debug should be False in production
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',  # Token authentication
    'drf_yasg',
    # Local apps
    'users',
    'movies',
    'bookings',
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

ROOT_URLCONF = 'movie_tix.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'movie_tix.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field
LOGIN_REDIRECT_URL = 'home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# TMDB API key - with multiple fallbacks to ensure it's loaded
TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '')

# If still not found, attempt multiple methods to get the API key
if not TMDB_API_KEY:
    # Method 1: Direct access from .env file in various locations
    try:
        import dotenv
        for env_path in [
            os.path.join(BASE_DIR, '.env'),
            os.path.join(BASE_DIR.parent, '.env'),
            os.path.join(os.getcwd(), '.env')
        ]:
            if os.path.exists(env_path):
                env_vars = dotenv.dotenv_values(env_path)
                if 'TMDB_API_KEY' in env_vars and env_vars['TMDB_API_KEY']:
                    TMDB_API_KEY = env_vars['TMDB_API_KEY']
                    print(f"Found TMDB_API_KEY in {env_path}: {TMDB_API_KEY[:4]}...")
                    # Also set it in environment for potential future use
                    os.environ['TMDB_API_KEY'] = TMDB_API_KEY
                    break
    except (ImportError, Exception) as e:
        print(f"Failed to load TMDB_API_KEY from .env files: {e}")
    
    # Method 2: Hardcoded fallback for development only - remove in production!
    if not TMDB_API_KEY:
        TMDB_API_KEY = '9c52f42462d276f88fc32d0f13411270'  # THIS IS A FALLBACK FOR DEVELOPMENT
        print(f"Using hardcoded TMDB_API_KEY fallback: {TMDB_API_KEY[:4]}...")
        
print(f"Final TMDB_API_KEY status: {'Found ('+TMDB_API_KEY[:4]+'...)' if TMDB_API_KEY else 'Not found'}")

# Email settings
EMAIL_BACKEND = 'django_ses.SESBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'movietix2123@gmail.com')

# AWS credentials for SES
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')

AWS_SES_REGION_NAME = os.environ.get('AWS_SES_REGION_NAME', 'us-east-1')
AWS_SES_REGION_ENDPOINT = f"email.{AWS_SES_REGION_NAME}.amazonaws.com"

# Stripe settings
STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')

# Celery settings (optional)
# To use Celery for background tasks:
# 1. Install Redis: https://redis.io/download
# 2. Install Celery: pip install celery redis
# 3. Start Redis server
# 4. Start Celery worker: celery -A movie_tix worker -l info
# If Celery/Redis is not available, the application will fall back to synchronous processing
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Site URL for email verification links
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000')


# Debug toolbar settings
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']
    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
    }

# REST framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# Swagger settings
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'basic': {
            'type': 'basic'
        },
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'Type in the *Value* input box below: **Bearer &lt;token&gt;**'
        },
    },
    'SECURITY_REQUIREMENTS': [
        {'Bearer': []},
    ],
    'USE_SESSION_AUTH': True,  # Enables Django login for Swagger UI
    'LOGIN_URL': '/login/',
    'LOGOUT_URL': '/logout/',
}
