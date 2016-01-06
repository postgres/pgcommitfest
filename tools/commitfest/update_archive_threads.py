#!/usr/bin/env python
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
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), '../../'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pgcommitfest.settings")
import django
django.setup()

from django.db import connection

from pgcommitfest.commitfest.models import MailThread
from pgcommitfest.commitfest.ajax import _archivesAPI, parse_and_add_attachments

if __name__ == "__main__":
	debug = "--debug" in sys.argv

	# Logging always done to stdout, but we can turn on/off how much
	logging.basicConfig(format='%(asctime)s %(levelname)s: %(msg)s',
						level=debug and logging.DEBUG or logging.INFO,
						stream=sys.stdout)

	logging.debug("Checking for updated mail threads in the archives")
	for thread in MailThread.objects.filter(patches__commitfests__status__in=(1,2,3)).distinct():
		logging.debug("Checking %s in the archives" % thread.messageid)
		r = sorted(_archivesAPI('/message-id.json/%s' % thread.messageid), key=lambda x: x['date'])
		if thread.latestmsgid != r[-1]['msgid']:
			# There is now a newer mail in the thread!
			logging.info("Thread %s updated" % thread.messageid)
			thread.latestmsgid = r[-1]['msgid']
			thread.latestmessage = r[-1]['date']
			thread.latestauthor = r[-1]['from']
			thread.latestsubject = r[-1]['subj']
			thread.save()
			parse_and_add_attachments(r, thread)
			# Potentially update the last mail date - if there wasn't already a mail on each patch
			# from a *different* thread that had an earlier date.
			for p in thread.patches.filter(lastmail__lt=thread.latestmessage):
				logging.debug("Last mail time updated for %s" % thread.messageid)
				p.lastmail = thread.latestmessage
				p.save()

	connection.close()
	logging.debug("Done.")
