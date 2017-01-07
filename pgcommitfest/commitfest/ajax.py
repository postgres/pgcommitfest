from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction

import httplib
import socket
import urllib
import json

from pgcommitfest.auth import user_search

class HttpResponseServiceUnavailable(HttpResponse): 
	status_code = 503

class Http503(Exception):
	pass

from models import CommitFest, Patch, MailThread, MailThreadAttachment
from models import MailThreadAnnotation, PatchHistory

def _archivesAPI(suburl, params=None):
	try:
		socket.setdefaulttimeout(settings.ARCHIVES_TIMEOUT)
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
		if params:
			url = "%s?%s" % (suburl, urllib.urlencode(params))
		else:
			url = suburl
		h.request('GET', url, headers={
			'Host': settings.ARCHIVES_HOST,
			})
		resp = h.getresponse()
		if resp.status != 200:
			if resp.status == 404:
				raise Http404()
			raise Exception("JSON call failed: %s" % resp.status)

		r = json.load(resp)
		resp.close()
		h.close()
	except socket.error, e:
		raise Http503("Failed to communicate with archives backend: %s" % e)
	return r

def getThreads(request):
	search = request.GET.has_key('s') and request.GET['s'] or None
	if request.GET.has_key('a') and request.GET['a'] == "1":
		attachonly = 1
	else:
		attachonly = 0

	# Make a JSON api call to the archives server
	params = {'n': 100, 'a': attachonly}
	if search:
		params['s'] = search

	r = _archivesAPI('/list/pgsql-hackers/latest.json', params)
	return sorted(r, key=lambda x: x['date'], reverse=True)

def getMessages(request):
	threadid = request.GET['t']

	thread = MailThread.objects.get(pk=threadid)

	# Always make a call over to the archives api
	r = _archivesAPI('/message-id.json/%s' % thread.messageid)
	return sorted(r, key=lambda x: x['date'], reverse=True)

@transaction.atomic
def annotateMessage(request):
	thread = get_object_or_404(MailThread, pk=int(request.POST['t']))
	msgid = request.POST['msgid']
	msg = request.POST['msg']

	# Get the subject, author and date from the archives
	# We only have an API call to get the whole thread right now, so
	# do that, and then find our entry in it.
	r = _archivesAPI('/message-id.json/%s' % thread.messageid)
	for m in r:
		if m['msgid'] == msgid:
			annotation = MailThreadAnnotation(mailthread=thread,
											  user=request.user,
											  msgid=msgid,
											  annotationtext=msg,
											  mailsubject=m['subj'],
											  maildate=m['date'],
											  mailauthor=m['from'])
			annotation.save()

			for p in thread.patches.all():
				PatchHistory(patch=p, by=request.user, what='Added annotation "%s" to %s' % (msg, msgid)).save_and_notify()
				p.set_modified()
				p.save()

			return 'OK'
	return 'Message not found in thread!'

@transaction.atomic
def deleteAnnotation(request):
	annotation = get_object_or_404(MailThreadAnnotation, pk=request.POST['id'])

	for p in annotation.mailthread.patches.all():
		PatchHistory(patch=p, by=request.user, what='Deleted annotation "%s" from %s' % (annotation.annotationtext, annotation.msgid)).save_and_notify()
		p.set_modified()
		p.save()

	annotation.delete()

	return 'OK'

def parse_and_add_attachments(threadinfo, mailthread):
	for t in threadinfo:
		if len(t['atts']):
			# One or more attachments. For now, we're only actually going
			# to store and process the first one, even though the API gets
			# us all of them.
			MailThreadAttachment.objects.get_or_create(mailthread=mailthread,
													   messageid=t['msgid'],
													   defaults={
														   'date': t['date'],
														   'author': t['from'],
														   'attachmentid': t['atts'][0]['id'],
														   'filename': t['atts'][0]['name'],
													   })
		# In theory we should remove objects if they don't have an
		# attachment, but how could that ever happen? Ignore for now.

@transaction.atomic
def attachThread(request):
	cf = get_object_or_404(CommitFest, pk=int(request.POST['cf']))
	patch = get_object_or_404(Patch, pk=int(request.POST['p']), commitfests=cf)
	msgid = request.POST['msg']

	return doAttachThread(cf, patch, msgid, request.user)

def doAttachThread(cf, patch, msgid, user):
	# Note! Must be called in an open transaction!
	r = sorted(_archivesAPI('/message-id.json/%s' % msgid), key=lambda x: x['date'])
	# We have the full thread metadata - using the first and last entry,
	# construct a new mailthread in our own model.
	# First, though, check if it's already there.
	threads = MailThread.objects.filter(messageid=r[0]['msgid'])
	if len(threads):
		thread = threads[0]
		if thread.patches.filter(id=patch.id).exists():
			return 'This thread is already added to this email'

		# We did not exist, so we'd better add ourselves.
		# While at it, we update the thread entry with the latest data from the
		# archives.
		thread.patches.add(patch)
		thread.latestmessage=r[-1]['date']
		thread.latestauthor=r[-1]['from']
		thread.latestsubject=r[-1]['subj']
		thread.latestmsgid=r[-1]['msgid']
		thread.save()
	else:
		# No existing thread existed, so create it
		# Now create a new mailthread entry
		m = MailThread(messageid=r[0]['msgid'],
					   subject=r[0]['subj'],
					   firstmessage=r[0]['date'],
					   firstauthor=r[0]['from'],
					   latestmessage=r[-1]['date'],
					   latestauthor=r[-1]['from'],
					   latestsubject=r[-1]['subj'],
					   latestmsgid=r[-1]['msgid'],
					   )
		m.save()
		m.patches.add(patch)
		m.save()
		parse_and_add_attachments(r, m)

	PatchHistory(patch=patch, by=user, what='Attached mail thread %s' % r[0]['msgid']).save_and_notify()
	patch.update_lastmail()
	patch.set_modified()
	patch.save()

	return 'OK'

@transaction.atomic
def detachThread(request):
	cf = get_object_or_404(CommitFest, pk=int(request.POST['cf']))
	patch = get_object_or_404(Patch, pk=int(request.POST['p']), commitfests=cf)
	thread = get_object_or_404(MailThread, messageid=request.POST['msg'])

	patch.mailthread_set.remove(thread)
	PatchHistory(patch=patch, by=request.user, what='Detached mail thread %s' % request.POST['msg']).save_and_notify()
	patch.update_lastmail()
	patch.set_modified()
	patch.save()

	return 'OK'

def searchUsers(request):
	if request.GET.has_key('s') and request.GET['s']:
		return user_search(request.GET['s'])
	else:
		return []

def importUser(request):
	if request.GET.has_key('u') and request.GET['u']:
		u = user_search(userid=request.GET['u'])
		if len (u) != 1:
			return "Internal error, duplicate user found"

		u = u[0]

		if User.objects.filter(username=u['u']).exists():
			return "User already exists"
		User(username=u['u'],
			 first_name=u['f'],
			 last_name=u['l'],
			 email=u['e'],
			 password='setbypluginnotsha1',
			 ).save()
		return 'OK'
	else:
		raise Http404()

_ajax_map={
	'getThreads': getThreads,
	'getMessages': getMessages,
	'attachThread': attachThread,
	'detachThread': detachThread,
	'annotateMessage': annotateMessage,
	'deleteAnnotation': deleteAnnotation,
	'searchUsers': searchUsers,
	'importUser': importUser,
}

# Main entrypoint for /ajax/<command>/
@csrf_exempt
@login_required
def main(request, command):
	if not _ajax_map.has_key(command):
		raise Http404
	try:
		resp = HttpResponse(content_type='application/json')
		json.dump(_ajax_map[command](request), resp)
		return resp
	except Http503, e:
		return HttpResponseServiceUnavailable(e, mimetype='text/plain')
