from .development import *

# Test settings for multi-DB
FILIALE_CONN_MAX_AGE = None
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'GM'),
        'USER': os.environ.get('DB_USER', 'gm_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', '1494.slk'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': None,
        'OPTIONS': {'connect_timeout': 10},
    }
}
DATABASES.update(build_filiale_databases(DATABASES['default']))
for alias in DATABASES:
    DATABASES[alias]['CONN_MAX_AGE'] = None
    DATABASES[alias].setdefault('TEST', {})
    DATABASES[alias]['TEST']['NAME'] = 'test_' + DATABASES[alias]['NAME']

