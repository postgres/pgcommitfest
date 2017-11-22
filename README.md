# CommitFest

This application manages commitfests for the PostgreSQL community.

A commitfest is a collection of patches and reviews for a project and is part of the PostgreSQL development process.

## The Application

This is a Django 1.8 application backed by PostgreSQL and running on Python 2.7.

## Getting Started

### Ubuntu instructions

First, prepare your development environment by installing pip, virtualenv, and postgresql-server-dev-X.Y.

```
$ sudo apt install python-pip postgresql-server-dev-9.6

$ pip install virtualenv
```

Next, configure your local environment with virtualenv and install local dependencies.

```
$ virtualenv env
$ source env/bin/activate
$ pip install -r requirements.txt
```

Now prepare the application to run locally.

Configure the app to match your local installation by creating a
`local_settings.py` with the following content in the `pgcommitfest` directory.
Change the values for the database connection adequately.

```
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
```

Provided that you created a database matching the above settings, you can
now create the required tables.

```
$ python manage.py migrate
```

You'll need either a database dump of the actual server's data or else to create a superuser:

```
$ python manage.py createsuperuser
```

Finally, you're ready to start the application:

```
$ python manage.py runserver
```

To authenticate you'll first have to remove the customized login template.
Remember not to commit this modification.

```
$ rm -rf global_templates/admin/login.html
```

Then open http://localhost:8000/admin to log in. Once redirected to the Django
admin interface, go back to the main interface. You're now logged in.
