#!/usr/bin/env python3
"""Run uWSGI with Django static files mapping.

The reason we don't hardcode the path to the static admin directory in the
uwsgi_dev.ini file is because the path contains the python version, something
like:

env/lib/python3.12/site-packages/django/...

Requiring everyone to use the same python version is not practical, so instead
we have this tiny script that will find the path to the Django admin static
files and run uWSGI with the correct path.
"""

from importlib.machinery import PathFinder
import subprocess
import sys

django_path = PathFinder().find_spec("django").submodule_search_locations[0]

django_admin_path = django_path + "/contrib/admin/static/admin"

if len(sys.argv) > 1:
    ini_file = sys.argv[1]
else:
    ini_file = "uwsgi_dev.ini"

subprocess.run(
    [
        "uwsgi",
        "--static-map",
        f"/media/admin={django_path}/contrib/admin/static/admin",
        ini_file,
    ]
)
