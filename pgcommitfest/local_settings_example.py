# Enable more debugging information
DEBUG = True
# Prevent logging to try to send emails to postgresql.org admins.
# Use the default Django logging settings instead.
LOGGING = None

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'pgcommitfest',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': '0.0.0.0',
    }
}

# Disables the PostgreSQL.ORG authentication.
# Use the default built-in Django authentication module.
AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']
