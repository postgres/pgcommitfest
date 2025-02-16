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
For a quick start, you can load some dummy data into the database. Here's how
you do that:

```bash
./manage.py loaddata auth_data.json
./manage.py loaddata commitfest_data.json
```

If you do this, the admin username and password are `admin` and `admin`. There
are a few other users as well (`staff`, `normal`, `committer`,
`inactive-committer`), that all have the same password as their username.

On the other hand, if you'd like to start from scratch instead, you can run the
following command to create a super user:

```bash
./manage.py createsuperuser
```

#### Start application
Finally, you're ready to start the application:

```bash
./run_dev.py
```

Then open http://localhost:8007/admin to log in. Once redirected to the Django
admin interface, go back to the main interface. You're now logged in.

## Contributing

Code formatting and linting is done using [`ruff`] and [`biome`]. You can run
formatting using `make format`. Linting can be done using `make lint` and
automatic fixing of linting errors can be done using `make lint-fix` or `make
lint-fix-unsafe` (unsafe fixes can slightly change program behaviour, but often
the fixed behaviour is the one you intended). You can also run both `make
format` and `make lint-fix-unsafe` together by using `make fix`. CI
automatically checks that you adhere to these coding standards.

You can install the git pre-commit hook to help you adhere to the codestyle:

```bash
ln -s ../../tools/githook/pre-commit .git/hooks/
```

[`ruff`]: https://docs.astral.sh/ruff/
[`biome`]: https://biomejs.dev/

### Discord

If you want to discuss development of a fix/feature over chat. Please join the
`#commitfest-dev` channel on the ["PostgreSQL Hacking" Discord server][1]

[1]: https://discord.gg/XZy2DXj7Wz

### Staging server

The staging server is available at: <https://commitfest-test.postgresql.org/>
User and password for the HTTP authentication popup are both `pgtest`. The
`main` branch is automatically deployed to the staging server. After some time
on the staging server, commits will be merged into the `prod` branch, which
automatically deploys to the production server.

### Regenerating the database dump files

If you'd like to regenerate the database dump files, you can run the following commands:
```
./manage.py dumpdata auth  --format=json --indent=4 --exclude=auth.permission > pgcommitfest/commitfest/fixtures/auth_data.json
./manage.py dumpdata commitfest  --format=json --indent=4 > pgcommitfest/commitfest/fixtures/commitfest_data.json
```

If you want to reload data from dump file, you can run `drop owned by postgres;` in the `pgcommitfest` database first.
