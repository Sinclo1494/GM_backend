from .base import *

DEBUG = True

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-key-change-in-production",
)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "GM"),
        "USER": os.environ.get("DB_USER", "gm_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "1494.slk"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

# Re-create the "filiale_<code>" connection aliases from the "default"
# connection above.  Without this the per-filiale databases are unknown to
# Django and every routed query raises ConnectionDoesNotExist.
DATABASES.update(build_filiale_databases(DATABASES["default"]))

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

LOGGING["handlers"]["console"]["level"] = "WARNING"
LOGGING["loggers"]["django.server"] = {
    "handlers": ["console"],
    "level": "WARNING",
    "propagate": False,
}
