import os

# Enable more debugging information
DEBUG = True
# Prevent logging to try to send emails to postgresql.org admins.
# Use the default Django logging settings instead.
LOGGING = None

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "pgcommitfest",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "0.0.0.0",
    }
}

# Disables the PostgreSQL.ORG authentication.
# Use the default built-in Django authentication module.
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

# The only login page we have in development is the Django admin login page.
# It's not great, because it won't redirect to the page you were trying to
# access, but it's better than a HTTP 500 error.
PGAUTH_REDIRECT = "/admin/login/"

MOCK_ARCHIVES = True
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOCK_ARCHIVE_DATA = os.path.join(
    BASE_DIR, "commitfest", "fixtures", "archive_data.json"
)

CFBOT_SECRET = "INSECURE"
CFBOT_API_URL = "http://localhost:5000/api"

# There are already commitfests in the default dummy database data.
# Automatically creating new ones would cause the ones that are visible on the
# homepage to have no data.
AUTO_CREATE_COMMITFESTS = False
