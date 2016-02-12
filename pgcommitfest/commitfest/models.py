from django.db import models
from django.contrib.auth.models import User

from datetime import datetime

from util import DiffableModel

# We have few enough of these, and it's really the only thing we
# need to extend from the user model, so just create a separate
# class.
class Committer(models.Model):
	user = models.OneToOneField(User, null=False, blank=False, primary_key=True)
	active = models.BooleanField(null=False, blank=False, default=True)

	def __unicode__(self):
		return unicode(self.user)

	@property
	def fullname(self):
		return "%s %s (%s)" % (self.user.first_name, self.user.last_name, self.user.username)

	class Meta:
		ordering = ('user__last_name', 'user__first_name')

class CommitFest(models.Model):
	STATUS_FUTURE=1
	STATUS_OPEN=2
	STATUS_INPROGRESS=3
	STATUS_CLOSED=4
	_STATUS_CHOICES = (
		(STATUS_FUTURE, 'Future'),
		(STATUS_OPEN, 'Open'),
		(STATUS_INPROGRESS, 'In Progress'),
		(STATUS_CLOSED, 'Closed'),
		)
	name = models.CharField(max_length=100, blank=False, null=False, unique=True)
	status = models.IntegerField(null=False, blank=False, default=1, choices=_STATUS_CHOICES)
	startdate = models.DateField(blank=True, null=True)
	enddate = models.DateField(blank=True, null=True)

	@property
	def statusstring(self):
		return [v for k,v in self._STATUS_CHOICES if k==self.status][0]

	@property
	def periodstring(self):
		if self.startdate and self.enddate:
			return "{0} - {1}".format(self.startdate, self.enddate)
		return ""

	@property
	def title(self):
		return "Commitfest %s" % self.name

	@property
	def isopen(self):
		return self.status == self.STATUS_OPEN

	def __unicode__(self):
		return self.name

	class Meta:
		verbose_name_plural='Commitfests'
		ordering = ('-startdate',)

class Topic(models.Model):
	topic = models.CharField(max_length=100, blank=False, null=False)

	def __unicode__(self):
		return self.topic


class Patch(models.Model, DiffableModel):
	name = models.CharField(max_length=500, blank=False, null=False, verbose_name='Description')
	topic = models.ForeignKey(Topic, blank=False, null=False)

	# One patch can be in multiple commitfests, if it has history
	commitfests = models.ManyToManyField(CommitFest, through='PatchOnCommitFest')

	# If there is a wiki page discussing this patch
	wikilink = models.URLField(blank=True, null=True, default='')

	# If there is a git repo about this patch
	gitlink = models.URLField(blank=True, null=True, default='')

	# Mailthreads are ManyToMany in the other direction
	#mailthreads_set = ...

	authors = models.ManyToManyField(User, related_name='patch_author', blank=True)
	reviewers = models.ManyToManyField(User, related_name='patch_reviewer', blank=True)

	committer = models.ForeignKey(Committer, blank=True, null=True)

	# Datestamps for tracking activity
	created = models.DateTimeField(blank=False, null=False, auto_now_add=True)
	modified = models.DateTimeField(blank=False, null=False)

	# Materialize the last time an email was sent on any of the threads
	# that's attached to this message.
	lastmail = models.DateTimeField(blank=True, null=True)

	map_manytomany_for_diff = {
		'authors': 'authors_string',
		'reviewers': 'reviewers_string',
		}
	# Some accessors
	@property
	def authors_string(self):
		return ", ".join(["%s %s (%s)" % (a.first_name, a.last_name, a.username) for a in self.authors.all()])

	@property
	def reviewers_string(self):
		return ", ".join(["%s %s (%s)" % (a.first_name, a.last_name, a.username) for a in self.reviewers.all()])

	@property
	def history(self):
		# Need to wrap this in a function to make sure it calls
		# select_related() and doesn't generate a bazillion queries
		return self.patchhistory_set.select_related('by').all()

	def set_modified(self, newmod=None):
		# Set the modified date to newmod, but only if that's newer than
		# what's currently set. If newmod is not specified, use the
		# current timestamp.
		if not newmod:
			newmod = datetime.now()
		if not self.modified or newmod > self.modified:
			self.modified = newmod

	def update_lastmail(self):
		# Update the lastmail field, based on the newest email in any of
		# the threads attached to it.
		threads = list(self.mailthread_set.all())
		if len(threads) == 0:
			self.lastmail = None
		else:
			self.lastmail = max(threads, key=lambda t:t.latestmessage).latestmessage

	def __unicode__(self):
		return self.name

	class Meta:
		verbose_name_plural = 'patches'

class PatchOnCommitFest(models.Model):
	# NOTE! This is also matched by the commitfest_patchstatus table,
	# but we hardcoded it in here simply for performance reasons since
	# the data should be entirely static. (Yes, that's something we
	# might re-evaluate in the future)
	STATUS_REVIEW=1
	STATUS_AUTHOR=2
	STATUS_COMMITTER=3
	STATUS_COMMITTED=4
	STATUS_NEXT=5
	STATUS_REJECTED=6
	STATUS_RETURNED=7
	_STATUS_CHOICES=(
		(STATUS_REVIEW, 'Needs review'),
		(STATUS_AUTHOR, 'Waiting on Author'),
		(STATUS_COMMITTER, 'Ready for Committer'),
		(STATUS_COMMITTED, 'Committed'),
		(STATUS_NEXT, 'Moved to next CF'),
		(STATUS_REJECTED, 'Rejected'),
		(STATUS_RETURNED, 'Returned with feedback')
	)
	_STATUS_LABELS=(
		(STATUS_REVIEW, 'default'),
		(STATUS_AUTHOR, 'primary'),
		(STATUS_COMMITTER, 'info'),
		(STATUS_COMMITTED, 'success'),
		(STATUS_NEXT, 'warning'),
		(STATUS_REJECTED, 'danger'),
		(STATUS_RETURNED, 'danger'),
	)
	OPEN_STATUSES=(STATUS_REVIEW, STATUS_AUTHOR, STATUS_COMMITTER)
	OPEN_STATUS_CHOICES=[x for x in _STATUS_CHOICES if x[0] in OPEN_STATUSES]

	patch = models.ForeignKey(Patch, blank=False, null=False)
	commitfest = models.ForeignKey(CommitFest, blank=False, null=False)
	enterdate = models.DateTimeField(blank=False, null=False)
	leavedate = models.DateTimeField(blank=True, null=True)

	status = models.IntegerField(blank=False, null=False, default=STATUS_REVIEW, choices=_STATUS_CHOICES)

	@property
	def is_closed(self):
		return self.status not in self.OPEN_STATUSES

	@property
	def statusstring(self):
		return [v for k,v in self._STATUS_CHOICES if k==self.status][0]

	class Meta:
		unique_together = (('patch', 'commitfest',),)
		ordering = ('-commitfest__startdate', )

class PatchHistory(models.Model):
	patch = models.ForeignKey(Patch, blank=False, null=False)
	date = models.DateTimeField(blank=False, null=False, auto_now_add=True)
	by = models.ForeignKey(User, blank=False, null=False)
	what = models.CharField(max_length=500, null=False, blank=False)

	@property
	def by_string(self):
		return "%s %s (%s)" % (self.by.first_name, self.by.last_name, self.by.username)

	def __unicode__(self):
		return "%s - %s" % (self.patch.name, self.date)

	class Meta:
		ordering = ('-date', )

class MailThread(models.Model):
	# This class tracks mail threads from the main postgresql.org
	# mailinglist archives. For each thread, we store *one* messageid.
	# Using this messageid we can always query the archives for more
	# detailed information, which is done dynamically as the page
	# is loaded.
	# For threads in an active or future commitfest, we also poll
	# the archives to fetch "updated entries" at (ir)regular intervals
	# so we can keep track of when there was last a change on the
	# thread in question.
	messageid = models.CharField(max_length=1000, null=False, blank=False, unique=True)
	patches = models.ManyToManyField(Patch, blank=False, null=False)
	subject = models.CharField(max_length=500, null=False, blank=False)
	firstmessage = models.DateTimeField(null=False, blank=False)
	firstauthor = models.CharField(max_length=500, null=False, blank=False)
	latestmessage = models.DateTimeField(null=False, blank=False)
	latestauthor = models.CharField(max_length=500, null=False, blank=False)
	latestsubject = models.CharField(max_length=500, null=False, blank=False)
	latestmsgid = models.CharField(max_length=1000, null=False, blank=False)

	def __unicode__(self):
		return self.subject

	class Meta:
		ordering = ('firstmessage', )

class MailThreadAttachment(models.Model):
	mailthread = models.ForeignKey(MailThread, null=False, blank=False)
	messageid = models.CharField(max_length=1000, null=False, blank=False)
	attachmentid = models.IntegerField(null=False, blank=False)
	filename = models.CharField(max_length=1000, null=False, blank=True)
	date = models.DateTimeField(null=False, blank=False)
	author = models.CharField(max_length=500, null=False, blank=False)
	ispatch = models.NullBooleanField()

	class Meta:
		ordering = ('-date',)
		unique_together = (('mailthread', 'messageid',), )

class MailThreadAnnotation(models.Model):
	mailthread = models.ForeignKey(MailThread, null=False, blank=False)
	date = models.DateTimeField(null=False, blank=False, auto_now_add=True)
	user = models.ForeignKey(User, null=False, blank=False)
	msgid = models.CharField(max_length=1000, null=False, blank=False)
	annotationtext = models.TextField(null=False, blank=False, max_length=2000)
	mailsubject = models.CharField(max_length=500, null=False, blank=False)
	maildate = models.DateTimeField(null=False, blank=False)
	mailauthor = models.CharField(max_length=500, null=False, blank=False)

	@property
	def user_string(self):
		return "%s %s (%s)" % (self.user.first_name, self.user.last_name, self.user.username)

	class Meta:
		ordering = ('date', )

class PatchStatus(models.Model):
	status = models.IntegerField(null=False, blank=False, primary_key=True)
	statusstring = models.TextField(max_length=50, null=False, blank=False)
	sortkey = models.IntegerField(null=False, blank=False, default=10)
