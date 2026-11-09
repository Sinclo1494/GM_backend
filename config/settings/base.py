import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

# Ensure PostgreSQL/libpq client messages are decoded as UTF-8 on Windows
# servers with non-UTF8 locales; without this, psycopg2 can raise
# UnicodeDecodeError while surfacing the real connection error.
os.environ.setdefault("PGCLIENTENCODING", "UTF8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = "django-insecure-dev-only-key-change-in-production"

DEBUG = False

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "api",
    "import_export",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "api.middleware.FilialeRoutingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "api/templates/api")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "gm_db"),
        "USER": os.environ.get("DB_USER", "gm_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "connect_timeout": 10,
            "client_encoding": "UTF8",
            "options": "-c client_encoding=UTF8 -c lc_messages=C",
        },
    }
}

# ---------------------------------------------------------------------------
# Per-filiale databases (one physical PostgreSQL database per filiale).
#
# Register each existing filiale here as: "<code_filiale>": "<database_name>".
# Max 10 filiales. No auto-provisioning; databases must already exist with
# identical schemas. Keys must match Filiale.code_filiale values.
#
# Example:
#   FILIALE_DATABASES = {
#       "P": "gm_filiale_p",
#       "A": "gm_filiale_a",
#   }
#
# A named connection "filiale_<code>" is created for each entry so the router
# can route operations to the right database. settings.DATABASES is NOT mutated
# at runtime.
# ---------------------------------------------------------------------------
FILIALE_DATABASES = {
    "A": "gm_a",
    "C": "gm_c",
    "E": "gm_e",
    "G": "gm_g",
    "K": "gm_k",
    "L": "gm_l",
    "M": "gm_m",
    "P": "gm_p",
    "R": "gm_r",
    "T": "gm_t",
}

# ---------------------------------------------------------------------------
# Connection lifetime of the per-filiale aliases.
#
# Every alias points at the SAME PostgreSQL server, and `max_connections` is
# a per-server budget, not a per-database one: the central database and the
# ten affiliate databases share the same slots.  A request can also open
# several affiliate connections at once (the all-filiales branch of the
# analysis views queries every affiliate in turn), and Django only reaps a
# connection when the thread that owns it handles another request, so a
# connection owned by a slow thread outlives CONN_MAX_AGE.
#
# The pile-up reached the server limit and every endpoint answered
# "FATAL: remaining connection slots are reserved for roles with the
# SUPERUSER attribute" (HTTP 500).  Affiliate connections are therefore
# closed at the end of the request that opened them: 0 means "close on
# request end" in Django.
#
# The central "default" connection keeps its own lifetime (see CONN_MAX_AGE
# in DATABASES): it is touched by every request, and one connection per
# worker thread is cheap and bounded.
# ---------------------------------------------------------------------------
FILIALE_CONN_MAX_AGE = 0

for _filiale_code, _filiale_db_name in FILIALE_DATABASES.items():
    DATABASES[f"filiale_{_filiale_code}"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _filiale_db_name,
        "USER": os.environ.get("DB_USER", "gm_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": FILIALE_CONN_MAX_AGE,
        "OPTIONS": {
            "connect_timeout": 10,
            "client_encoding": "UTF8",
            "options": "-c client_encoding=UTF8 -c lc_messages=C",
        },
    }


def build_filiale_databases(default_params):
    """
    Build the per-filiale connection aliases from the "default" connection.

    Sub-settings modules (development / production) replace DATABASES with
    their own "default" entry.  They MUST call this helper afterwards,
    otherwise the "filiale_<code>" aliases disappear and every router query
    raises ConnectionDoesNotExist.

    The affiliate aliases get their own ``CONN_MAX_AGE`` (see
    ``FILIALE_CONN_MAX_AGE``): copying the central connection's lifetime
    would let every worker thread hold an affiliate connection set alive
    indefinitely, and all the aliases share the same server-wide
    ``max_connections`` budget.
    """
    databases = {}
    for code, db_name in FILIALE_DATABASES.items():
        params = dict(default_params)
        params["NAME"] = db_name
        params["CONN_MAX_AGE"] = FILIALE_CONN_MAX_AGE
        databases[f"filiale_{code}"] = params
    return databases


# When True, affiliate-scoped models that cannot be routed to an affiliate
# database fall back to the central "default" database instead of raising.
# Set to False for a strict fail-closed setup (DatabaseRoutingError).
FILIALE_ROUTING_FALLBACK_TO_CENTRAL = True

# Explicit model-to-database map consumed by FailClosedDatabaseRouter.
# Models here always use the central "default" database. All other business
# models are filiale-scoped and fail closed to their user's filiale database.
CENTRAL_DB_MODELS = {
    "auth.user",
    "auth.group",
    "auth.permission",
    "contenttypes.contenttype",
    "sessions.session",
    "api.userprofile",
    "api.filiale",
    "api.entreprise",
    "api.division",
    "api.famille_structures",
    "api.journal",
    "api.notification",
}

# ---------------------------------------------------------------------------
# Database routing
# ---------------------------------------------------------------------------
DATABASE_ROUTERS = ["api.multidb.FailClosedDatabaseRouter"]

# Cache for the dashboard v2 aggregations (expensive rankings).
# LocMemCache is the Django default; keep it per-process safe and cheap.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dashboard-v2",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "fr"
USE_I18N = True
LANGUAGES = [("fr", "Français")]
TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = os.environ.get("DJANGO_STATIC_ROOT", os.path.join(BASE_DIR, "staticfiles"))
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "api/static"),
]

MEDIA_URL = "media/"
MEDIA_ROOT = os.environ.get("DJANGO_MEDIA_ROOT", os.path.join(BASE_DIR, "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "api.authentication.ExternalServiceJWTAuthentication",
        "api.authentication.FilialeAwareJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=180),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
CORS_ALLOWED_ORIGINS = [h.strip() for h in CORS_ALLOWED_ORIGINS if h.strip()]

CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
CSRF_TRUSTED_ORIGINS = [h.strip() for h in CSRF_TRUSTED_ORIGINS if h.strip()]

SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

LOG_DIR = os.environ.get("DJANGO_LOG_DIR", os.path.join(BASE_DIR, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file_app": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "django_app.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "file_error": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "django_error.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "console": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["file_app", "file_error", "console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["file_app", "file_error", "console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "api": {
            "handlers": ["file_app", "file_error", "console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

HEALTH_CHECK_ENABLED = os.environ.get("HEALTH_CHECK_ENABLED", "true").lower() == "true"
