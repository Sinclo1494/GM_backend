import secrets
import string

from django.contrib.auth.hashers import check_password, make_password


CLIENT_ID_ALPHABET = string.ascii_letters + string.digits
CLIENT_SECRET_ALPHABET = string.ascii_letters + string.digits + "-_"


def generate_client_id(length=32):
    return "svc_" + "".join(secrets.choice(CLIENT_ID_ALPHABET) for _ in range(length))


def generate_client_secret(length=48):
    return "".join(secrets.choice(CLIENT_SECRET_ALPHABET) for _ in range(length))


def hash_secret(secret):
    return make_password(secret)


def verify_secret(secret, hashed):
    return check_password(secret, hashed)
