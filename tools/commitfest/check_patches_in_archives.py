#!/usr/bin/env python3
#
# check_patches_in_archives.py
#
# Download and check attachments in the archives, to see if they are
# actually patches. We do this asynchronously in a separate script
# so we don't block the archives unnecessarily.
#

import logging
import os
import sys

import magic
import requests

# Set up for accessing django
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), "../../"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pgcommitfest.settings")
import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402

from pgcommitfest.commitfest.models import MailThreadAttachment  # noqa: E402

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    debug = "--debug" in sys.argv

    # Logging always done to stdout, but we can turn on/off how much
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(msg)s",
        level=debug and logging.DEBUG or logging.INFO,
        stream=sys.stdout,
    )

    mag = magic.open(magic.MIME)
    mag.load()

    logger.debug("Updating attachment metadata from archives")

    # Try to fetch/scan all attachments that haven't already been scanned.
    # If they have already been scanned, we don't bother.
    # We will hit the archives without delay when doing this, but that
    # should generally not be a problem because it's not going to be
    # downloading a lot...
    for a in MailThreadAttachment.objects.filter(ispatch__isnull=True):
        url = f"/message-id/attachment/{a.attachmentid}/attach"
        logger.debug(f"Checking attachment {a.attachmentid}")

        resp = requests.get(
            f"{'https' if settings.ARCHIVES_PORT == 443 else 'http'}://"
            f"{settings.ARCHIVES_SERVER}:{settings.ARCHIVES_PORT}{url}",
            headers={
                "Host": settings.ARCHIVES_HOST,
            },
            timeout=settings.ARCHIVES_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.error(f"Failed to get {url}: {resp.status_code}")
            continue

        # Attempt to identify the file using magic information
        mtype = mag.buffer(resp.content)
        logger.debug(f"Detected MIME type is {mtype}")

        # We don't support gzipped or tar:ed patches or anything like
        # that at this point - just plain patches.
        if mtype.startswith("text/x-diff"):
            a.ispatch = True
        else:
            a.ispatch = False
        logger.info(f"Attachment {a.id} is patch: {a.ispatch}")
        a.save()

    connection.close()
    logger.debug("Done.")
