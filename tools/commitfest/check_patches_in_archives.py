#!/usr/bin/env python
#
# check_patches_in_archives.py
#
# Download and check attachments in the archives, to see if they are
# actually patches. We do this asynchronously in a separate script
# so we don't block the archives unnecessarily.
#

import os
import sys
import socket
import httplib
import magic
import logging

# Set up for accessing django
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), '../../'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pgcommitfest.settings")
import django
django.setup()

from django.db import connection
from django.conf import settings

from pgcommitfest.commitfest.models import MailThreadAttachment

if __name__ == "__main__":
	debug = "--debug" in sys.argv

	# Logging always done to stdout, but we can turn on/off how much
	logging.basicConfig(format='%(asctime)s %(levelname)s: %(msg)s',
						level=debug and logging.DEBUG or logging.INFO,
						stream=sys.stdout)

	socket.setdefaulttimeout(settings.ARCHIVES_TIMEOUT)
	mag = magic.open(magic.MIME)
	mag.load()

	logging.debug("Updating attachment metadata from archives")

	# Try to fetch/scan all attachments that haven't already been scanned.
	# If they have already been scanned, we don't bother.
	# We will hit the archives without delay when doing this, but that
	# should generally not be a problem because it's not going to be
	# downloading a lot...
	for a in MailThreadAttachment.objects.filter(ispatch=None):
		url = "/message-id/attachment/%s/attach" % a.attachmentid
		logging.debug("Checking attachment %s" % a.attachmentid)

		if settings.ARCHIVES_PORT != 443:
			h = httplib.HTTPConnection(host=settings.ARCHIVES_SERVER,
									   port=settings.ARCHIVES_PORT,
									   strict=True,
									   timeout=settings.ARCHIVES_TIMEOUT)
		else:
			h = httplib.HTTPSConnection(host=settings.ARCHIVES_SERVER,
									   port=settings.ARCHIVES_PORT,
									   strict=True,
									   timeout=settings.ARCHIVES_TIMEOUT)
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

		# Attempt to identify the file using magic information
		mtype = mag.buffer(contents)
		logging.debug("Detected MIME type is %s" % mtype)

		# We don't support gzipped or tar:ed patches or anything like
		# that at this point - just plain patches.
		if mtype.startswith('text/x-diff'):
			a.ispatch = True
		else:
			a.ispatch = False
		logging.info("Attachment %s is patch: %s" % (a.id, a.ispatch))
		a.save()

	connection.close()
	logging.debug("Done.")
