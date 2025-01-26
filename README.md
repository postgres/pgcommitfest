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
You can either start from scratch, in which case you'll create a superuser like so:
create a super user:

```bash
./manage.py createsuperuser
```

On the other hand, you can use some dummy data instead. Here's how you do that.

```
./manage.py loaddata auth_data.json
./manage.py loaddata commitfest_data.json
```

If you do this, the admin username and password are `admin` and `admin`.


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

If you'd like to regenerate the database dump files, you can run the following commands:
```
./manage.py dumpdata auth  --format=json --indent=4 > pgcommitfest/commitfest/fixtures/auth_data.json
./manage.py dumpdata commitfest  --format=json --indent=4  --exclude=commitfest.MailThread --exclude=commitfest.MailThreadAttachment > pgcommitfest/commitfest/fixtures/commitfest_data.json
```

Note that at present, we exclude the MailThread model because it leads to a recursion error.
In general, working with the mailing list is a bit delicate because we're also mocking the archives server,
so if you need to dump or load mailing thread data, you may run into errors that require manual adjustments.

If you want to reload data from dump file, you can run `drop owned by postgres;` in the `pgcommitfest` database first.
