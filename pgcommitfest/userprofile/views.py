from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings

from datetime import datetime

from pgcommitfest.mailqueue.util import send_template_mail

from models import UserProfile, UserExtraEmail
from forms import UserProfileForm, MailForm
from util import generate_random_token

@login_required
@transaction.commit_on_success
def userprofile(request):
	(profile, created) = UserProfile.objects.get_or_create(user=request.user)
	form = mailform = None

	if request.method == 'POST':
		if request.POST['submit'] == 'Save':
			form = UserProfileForm(request.user, request.POST, instance=profile)
			if form.is_valid():
				form.save()
				messages.add_message(request, messages.INFO, "User profile saved.")
				return HttpResponseRedirect('.')
		elif request.POST['submit'] == 'Add email':
			mailform = MailForm(request.POST)
			if mailform.is_valid():
				m = UserExtraEmail(user=request.user,
								   email=mailform.cleaned_data['email'],
								   confirmed=False,
								   token=generate_random_token(),
								   tokensent=datetime.now())
				m.save()
				send_template_mail(settings.NOTIFICATION_FROM,
								   request.user.username,
								   m.email,
								   'Your email address for commitfest.postgresql.org',
								   'extra_email_mail.txt',
								   {'token': m.token, 'user': m.user})
				messages.info(request, "A confirmation token has been sent to %s" % m.email)
				return HttpResponseRedirect('.')
		else:
			messages.error(request, "Invalid submit button pressed! Nothing saved.")
			return HttpResponseRedirect('.')

	if not form:
		form = UserProfileForm(request.user, instance=profile)
	if not mailform:
		mailform = MailForm()

	extramails = UserExtraEmail.objects.filter(user=request.user)

	return render_to_response('userprofileform.html', {
		'form': form,
		'extramails': extramails,
		'mailform': mailform,
		}, context_instance=RequestContext(request))

@login_required
@transaction.commit_on_success
def deletemail(request):
	try:
		id = int(request.META['QUERY_STRING'])
	except ValueError:
		messages.error(request, "Invalid format of id in query string")
		return HttpResponseRedirect('../')

	try:
		e = UserExtraEmail.objects.get(user=request.user, id=id)
	except UserExtraEmail.DoesNotExist:
		messages.error(request, "Specified email address does not exist on this user")
		return HttpResponseRedirect('../')

	messages.info(request, "Email address %s deleted." % e.email)
	e.delete()
	return HttpResponseRedirect('../')

@login_required
@transaction.commit_on_success
def confirmemail(request, tokenhash):
	try:
		e = UserExtraEmail.objects.get(user=request.user, token=tokenhash)
		if e.confirmed:
			messages.warning(request, "This email address has already been confirmed.")
		else:
			# Ok, it's not confirmed. So let's do that now
			e.confirmed = True
			e.token = ''
			e.save()
			messages.info(request, "Email address %s added to profile." % e.email)
	except UserExtraEmail.DoesNotExist:
		messages.error(request, "Token %s was not found for your user. It may be because it has already been used?" % tokenhash)

	return HttpResponseRedirect("../../")
