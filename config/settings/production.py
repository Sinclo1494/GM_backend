import os
from .base import *

if not os.environ.get("DJANGO_SECRET_KEY"):
    raise RuntimeError("DJANGO_SECRET_KEY environment variable is required in production")

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]

CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
CORS_ALLOWED_ORIGINS = [h.strip() for h in CORS_ALLOWED_ORIGINS if h.strip()]

CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
CSRF_TRUSTED_ORIGINS = [h.strip() for h in CSRF_TRUSTED_ORIGINS if h.strip()]

if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "False").lower() == "true"
    SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SESSION_COOKIE_SECURE", "True").lower() == "true"
    CSRF_COOKIE_SECURE = os.environ.get("DJANGO_CSRF_COOKIE_SECURE", "True").lower() == "true"
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "True").lower() == "true"
    SECURE_HSTS_PRELOAD = os.environ.get("DJANGO_SECURE_HSTS_PRELOAD", "False").lower() == "true"
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
