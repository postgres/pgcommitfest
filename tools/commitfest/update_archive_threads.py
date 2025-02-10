#!/usr/bin/env python3
#
# Update all attached mail threads from the archives.
#
# XXX: at some point we probably need to limit this so we don't hit all of them,
# at least not all of them all the time...
#

import os
import sys
import logging

# Set up for accessing django
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), "../../"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pgcommitfest.settings")
import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from pgcommitfest.commitfest.models import MailThread  # noqa: E402
from pgcommitfest.commitfest.ajax import refresh_single_thread  # noqa: E402

if __name__ == "__main__":
    debug = "--debug" in sys.argv

    # Logging always done to stdout, but we can turn on/off how much
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(msg)s",
        level=debug and logging.DEBUG or logging.INFO,
        stream=sys.stdout,
    )

    logging.debug("Checking for updated mail threads in the archives")
    for thread in MailThread.objects.filter(
        patches__commitfests__status__in=(1, 2, 3)
    ).distinct():
        logging.debug("Checking %s in the archives" % thread.messageid)
        refresh_single_thread(thread)

    connection.close()
    logging.debug("Done.")
