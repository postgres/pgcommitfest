#!/bin/bash
set -e

# Trivial update script for pgcf
if [ "$(id -u)" == "0" ]; then
    echo Do not run as root!
    exit 1
fi

cd $(dirname $0)

git pull --rebase

./python manage.py collectstatic --noinput

./python manage.py migrate

echo Done!
