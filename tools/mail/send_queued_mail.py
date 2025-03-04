#!/usr/bin/env python3
#
# Script to send off all queued email.
#
# This script is intended to be run frequently from cron. We queue things
# up in the db so that they get automatically rolled back as necessary,
# but once we reach this point we're just going to send all of them one
# by one.
#

import sys
import os
import smtplib

# Set up to run in django environment
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), "../../"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pgcommitfest.settings")
import django  # noqa: E402

django.setup()

from django.db import connection, transaction  # noqa: E402

from pgcommitfest.mailqueue.models import QueuedMail  # noqa: E402

if __name__ == "__main__":
    # Grab advisory lock, if available. Lock id is just a random number
    # since we only need to interlock against ourselves. The lock is
    # automatically released when we're done.
    curs = connection.cursor()
    curs.execute("SELECT pg_try_advisory_lock(72181379)")
    if not curs.fetchall()[0][0]:
        print("Failed to get advisory lock, existing send_queued_mail process stuck?")
        connection.close()
        sys.exit(1)

    for m in QueuedMail.objects.all():
        # Yes, we do a new connection for each run. Just because we can.
        # If it fails we'll throw an exception and just come back on the
        # next cron job. And local delivery should never fail...
        smtp = smtplib.SMTP("localhost")
        smtp.sendmail(m.sender, m.receiver, m.fullmsg.encode("utf-8"))
        smtp.close()
        m.delete()
        transaction.commit()
    connection.close()
