# CommitFest

This application manages commitfests for the PostgreSQL community.

A commitfest is a collection of patches and reviews for a project and is part of the PostgreSQL development process.

## The Application

This is a Django 4.2 application backed by PostgreSQL and running on Python 3.x.

## Getting Started

### Ubuntu instructions

#### Install Dependencies / Configure Environment

First, prepare your development environment by installing pip, virtualenv, and postgresql-server-dev-X.Y.

```bash
sudo apt install python-pip postgresql-server-dev-14
```

Next, configure your local environment with virtualenv and install local dependencies.

```bash
python3 -m venv env
source env/bin/activate
pip install -r dev_requirements.txt
```

Create a database for the application:

```bash
createdb pgcommitfest
```

Create a local settings file (feel free to edit it):

```bash
cp pgcommitfest/local_settings_example.py pgcommitfest/local_settings.py
```

Now you can now create the required tables. Note that a password might need to
be provided.

```bash
./manage.py migrate
```

#### Load data
You'll need either a database dump of the actual server's data or else to create a superuser. Here's how you
create a super user:

```bash
./manage.py createsuperuser
```

On the other hand, you can use some dummy data instead. Here's how you do that.

```
./manage.py loaddata auth_data.json
./manage.py loaddata commitfest_data.json
```

In the future, if you'd like to regenerate those database dump files, you can run the following commands:
```
./manage.py dumpdata auth  --format=json --indent=3 > pgcommitfest/commitfest/fixtures/auth_data.json
./manage.py dumpdata commitfest  --format=json --indent=3  --exclude=commitfest.MailThread > pgcommitfest/commitfest/fixtures/commitfest_data.json
```


#### Start application
Finally, you're ready to start the application:

```bash
./run_dev.py
```

Then open http://localhost:8007/admin to log in. Once redirected to the Django
admin interface, go back to the main interface. You're now logged in.

## Contributing

Before committing make sure to install the git pre-commit hook to adhere to the
codestyle.

```bash
ln -s ../../tools/githook/pre-commit .git/hooks/

```
