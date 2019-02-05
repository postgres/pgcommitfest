#!/usr/bin/env python
#
# update_attachment_filenames.py

# Go through all old attachments in the system and update the filename based on
# the information in the archives. Required after we added the filename field
# to attachments.
#

import os
import sys
import socket
import httplib
import magic
import logging

import simplejson

# Set up for accessing django
from django.core.management import setup_environ
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), '../../../pgcommitfest'))
import settings
setup_environ(settings)

from django.db import connection

from commitfest.models import MailThreadAttachment

if __name__ == "__main__":
    debug = "--debug" in sys.argv

    # Logging always done to stdout, but we can turn on/off how much
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(msg)s',
                        level=debug and logging.DEBUG or logging.INFO,
                        stream=sys.stdout)

    socket.setdefaulttimeout(settings.ARCHIVES_TIMEOUT)
    mag = magic.open(magic.MIME)
    mag.load()

    logging.info("Fetching attachment filenames from archives")

    for a in MailThreadAttachment.objects.filter(filename=""):
        url = "/message-id.json/%s" % a.messageid
        logging.debug("Checking attachment %s" % a.attachmentid)

        h = httplib.HTTPConnection(settings.ARCHIVES_SERVER,
                                   settings.ARCHIVES_PORT,
                                   True,
                                   settings.ARCHIVES_TIMEOUT)
        h.request('GET', url, headers={
            'Host': settings.ARCHIVES_HOST,
        })
        resp = h.getresponse()
        if resp.status != 200:
            logging.error("Failed to get %s: %s" % (url, resp.status))
            continue

        contents = resp.read()
        resp.close()
        h.close()

        obj = simplejson.loads(contents)

        try:
            for msg in obj:
                for att in msg['atts']:
                    if att['id'] == a.attachmentid:
                        print "id %s, att id %s, filename %s" % (a.id, a.attachmentid, att['name'])
                        a.filename = att['name']
                        a.save()
                        raise StopIteration
            logging.error("No match found for attachmentid %s" % a.attachmentid)
        except StopIteration:
            # Success
            pass

    connection.close()
    logging.debug("Done.")
