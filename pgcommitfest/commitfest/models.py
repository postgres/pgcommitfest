from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404

from datetime import datetime

from pgcommitfest.userprofile.models import UserProfile

from .util import DiffableModel


# We have few enough of these, and it's really the only thing we
# need to extend from the user model, so just create a separate
# class.
class Committer(models.Model):
    user = models.OneToOneField(
        User, null=False, blank=False, primary_key=True, on_delete=models.CASCADE
    )
    active = models.BooleanField(null=False, blank=False, default=True)

    def __str__(self):
        return str(self.user)

    @property
    def fullname(self):
        return "%s %s (%s)" % (
            self.user.first_name,
            self.user.last_name,
            self.user.username,
        )

    class Meta:
        ordering = ("user__last_name", "user__first_name")


class CommitFest(models.Model):
    STATUS_FUTURE = 1
    STATUS_OPEN = 2
    STATUS_INPROGRESS = 3
    STATUS_CLOSED = 4
    STATUS_PARKED = 5
    _STATUS_CHOICES = (
        (STATUS_FUTURE, "Future"),
        (STATUS_OPEN, "Open"),
        (STATUS_INPROGRESS, "In Progress"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_PARKED, "Drafts"),
    )
    _STATUS_LABELS = (
        (STATUS_FUTURE, "default"),
        (STATUS_OPEN, "info"),
        (STATUS_INPROGRESS, "success"),
        (STATUS_CLOSED, "danger"),
        (STATUS_PARKED, "default"),
    )
    name = models.CharField(max_length=100, blank=False, null=False, unique=True)
    status = models.IntegerField(
        null=False, blank=False, default=1, choices=_STATUS_CHOICES
    )
    startdate = models.DateField(blank=True, null=True)
    enddate = models.DateField(blank=True, null=True)

    @property
    def statusstring(self):
        return [v for k, v in self._STATUS_CHOICES if k == self.status][0]

    @property
    def periodstring(self):
        # Current Workflow intent is to have all Committfest be time-bounded
        # but the information is just contextual so we still permit null
        if self.startdate and self.enddate:
            return "{0} - {1}".format(self.startdate, self.enddate)
        return ""

    @property
    def title(self):
        return "Commitfest %s" % self.name

    @property
    def isclosed(self):
        return self.status == self.STATUS_CLOSED

    @property
    def isopen(self):
        return self.status == self.STATUS_OPEN

    @property
    def isinprogress(self):
        return self.status == self.STATUS_INPROGRESS

    @property
    def isparked(self):
        return self.status == self.STATUS_PARKED

    def json(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.statusstring,
            "startdate": self.startdate.isoformat(),
            "enddate": self.enddate.isoformat(),
        }

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Commitfests"
        ordering = ("-startdate",)


class Topic(models.Model):
    topic = models.CharField(max_length=100, blank=False, null=False)

    def __str__(self):
        return self.topic


class TargetVersion(models.Model):
    version = models.CharField(max_length=8, blank=False, null=False, unique=True)

    class Meta:
        ordering = [
            "-version",
        ]

    def __str__(self):
        return self.version


class Patch(models.Model, DiffableModel):
    name = models.CharField(
        max_length=500, blank=False, null=False, verbose_name="Description"
    )
    topic = models.ForeignKey(Topic, blank=False, null=False, on_delete=models.CASCADE)

    # One patch can be in multiple commitfests, if it has history
    commitfests = models.ManyToManyField(CommitFest, through="PatchOnCommitFest")

    # If there is a wiki page discussing this patch
    wikilink = models.URLField(blank=True, null=False, default="")

    # If there is a git repo about this patch
    gitlink = models.URLField(blank=True, null=False, default="")

    # Version targeted by this patch
    targetversion = models.ForeignKey(
        TargetVersion,
        blank=True,
        null=True,
        verbose_name="Target version",
        on_delete=models.CASCADE,
    )

    authors = models.ManyToManyField(User, related_name="patch_author", blank=True)
    reviewers = models.ManyToManyField(User, related_name="patch_reviewer", blank=True)

    committer = models.ForeignKey(
        Committer, blank=True, null=True, on_delete=models.CASCADE
    )

    # Users to be notified when something happens
    subscribers = models.ManyToManyField(
        User, related_name="patch_subscriber", blank=True
    )

    mailthread_set = models.ManyToManyField(
        "MailThread",
        related_name="patches",
        blank=False,
        db_table="commitfest_mailthread_patches",
    )

    # Datestamps for tracking activity
    created = models.DateTimeField(blank=False, null=False, auto_now_add=True)
    modified = models.DateTimeField(blank=False, null=False, auto_now_add=True)

    # Materialize the last time an email was sent on any of the threads
    # that's attached to this message.
    lastmail = models.DateTimeField(blank=True, null=True)

    map_manytomany_for_diff = {
        "authors": "authors_string",
        "reviewers": "reviewers_string",
    }

    def current_commitfest(self):
        return self.current_patch_on_commitfest().commitfest

    def current_patch_on_commitfest(self):
        # The unique partial index poc_enforce_maxoneoutcome_idx stores the PoC
        # No caching here (inside the instance) since the caller should just need
        # the PoC once per request.
        return get_object_or_404(
            PatchOnCommitFest, Q(patch=self) & ~Q(status=PatchOnCommitFest.STATUS_NEXT)
        )

    # Some accessors
    @property
    def authors_string(self):
        return ", ".join(
            [
                "%s %s (%s)" % (a.first_name, a.last_name, a.username)
                for a in self.authors.all()
            ]
        )

    @property
    def reviewers_string(self):
        return ", ".join(
            [
                "%s %s (%s)" % (a.first_name, a.last_name, a.username)
                for a in self.reviewers.all()
            ]
        )

    @property
    def history(self):
        # Need to wrap this in a function to make sure it calls
        # select_related() and doesn't generate a bazillion queries
        return self.patchhistory_set.select_related("by").all()

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
            self.lastmail = max(threads, key=lambda t: t.latestmessage).latestmessage

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "patches"


class PatchOnCommitFest(models.Model):
    # NOTE! This is also matched by the commitfest_patchstatus table,
    # but we hardcoded it in here simply for performance reasons since
    # the data should be entirely static. (Yes, that's something we
    # might re-evaluate in the future)
    STATUS_REVIEW = 1
    STATUS_AUTHOR = 2
    STATUS_COMMITTER = 3
    STATUS_COMMITTED = 4
    STATUS_NEXT = 5
    STATUS_REJECTED = 6
    STATUS_RETURNED = 7
    STATUS_WITHDRAWN = 8
    _STATUS_CHOICES = (
        (STATUS_REVIEW, "Needs review"),
        (STATUS_AUTHOR, "Waiting on Author"),
        (STATUS_COMMITTER, "Ready for Committer"),
        (STATUS_COMMITTED, "Committed"),
        (STATUS_NEXT, "Moved to next CF"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_RETURNED, "Returned with feedback"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    )
    _STATUS_LABELS = (
        (STATUS_REVIEW, "default"),
        (STATUS_AUTHOR, "primary"),
        (STATUS_COMMITTER, "info"),
        (STATUS_COMMITTED, "success"),
        (STATUS_NEXT, "warning"),
        (STATUS_REJECTED, "danger"),
        (STATUS_RETURNED, "danger"),
        (STATUS_WITHDRAWN, "danger"),
    )
    OPEN_STATUSES = [STATUS_REVIEW, STATUS_AUTHOR, STATUS_COMMITTER]

    @classmethod
    def OPEN_STATUS_CHOICES(cls):
        return [x for x in cls._STATUS_CHOICES if x[0] in cls.OPEN_STATUSES]

    patch = models.ForeignKey(Patch, blank=False, null=False, on_delete=models.CASCADE)
    commitfest = models.ForeignKey(
        CommitFest, blank=False, null=False, on_delete=models.CASCADE
    )
    enterdate = models.DateTimeField(blank=False, null=False)
    leavedate = models.DateTimeField(blank=True, null=True)

    status = models.IntegerField(
        blank=False, null=False, default=STATUS_REVIEW, choices=_STATUS_CHOICES
    )

    @property
    def is_closed(self):
        return self.status not in self.OPEN_STATUSES

    @property
    def is_open(self):
        return not self.is_closed

    @property
    def is_committed(self):
        return self.status == self.STATUS_COMMITTED

    @property
    def needs_committer(self):
        return self.status == self.STATUS_COMMITTER

    @property
    def statusstring(self):
        return [v for k, v in self._STATUS_CHOICES if k == self.status][0]

    class Meta:
        unique_together = (
            (
                "patch",
                "commitfest",
            ),
        )
        ordering = ("-commitfest__startdate",)


class PatchHistory(models.Model):
    patch = models.ForeignKey(Patch, blank=False, null=False, on_delete=models.CASCADE)
    date = models.DateTimeField(
        blank=False, null=False, auto_now_add=True, db_index=True
    )
    by = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)
    by_cfbot = models.BooleanField(null=False, blank=False, default=False)
    what = models.CharField(max_length=500, null=False, blank=False)

    @property
    def by_string(self):
        if self.by_cfbot:
            return "CFbot"

        return "%s %s (%s)" % (self.by.first_name, self.by.last_name, self.by.username)

    def __str__(self):
        return "%s - %s" % (self.patch.name, self.date)

    class Meta:
        ordering = ("-date",)
        constraints = [
            models.CheckConstraint(
                check=(models.Q(by_cfbot=True) & models.Q(by__isnull=True))
                | (models.Q(by_cfbot=False) & models.Q(by__isnull=False)),
                name="check_by",
            ),
        ]

    def save_and_notify(
        self,
        prevcommitter=None,
        prevreviewers=None,
        prevauthors=None,
        authors_only=False,
    ):
        # Save this model, and then trigger notifications if there are any. There are
        # many different things that can trigger notifications, so try them all.
        self.save()

        recipients = []
        if not authors_only:
            recipients.extend(self.patch.subscribers.all())

            # Current or previous committer wants all notifications
            try:
                if (
                    self.patch.committer
                    and self.patch.committer.user.userprofile.notify_all_committer
                ):
                    recipients.append(self.patch.committer.user)
            except UserProfile.DoesNotExist:
                pass

            try:
                if (
                    prevcommitter
                    and prevcommitter.user.userprofile.notify_all_committer
                ):
                    recipients.append(prevcommitter.user)
            except UserProfile.DoesNotExist:
                pass

            # Current or previous reviewers wants all notifications
            recipients.extend(
                self.patch.reviewers.filter(userprofile__notify_all_reviewer=True)
            )
            if prevreviewers:
                # prevreviewers is a list
                recipients.extend(
                    User.objects.filter(
                        id__in=[p.id for p in prevreviewers],
                        userprofile__notify_all_reviewer=True,
                    )
                )

        # Current or previous authors wants all notifications
        recipients.extend(
            self.patch.authors.filter(userprofile__notify_all_author=True)
        )

        for u in set(recipients):
            if u != self.by:  # Don't notify for changes we make ourselves
                PendingNotification(history=self, user=u).save()


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
    subject = models.CharField(max_length=500, null=False, blank=False)
    firstmessage = models.DateTimeField(null=False, blank=False)
    firstauthor = models.CharField(max_length=500, null=False, blank=False)
    latestmessage = models.DateTimeField(null=False, blank=False)
    latestauthor = models.CharField(max_length=500, null=False, blank=False)
    latestsubject = models.CharField(max_length=500, null=False, blank=False)
    latestmsgid = models.CharField(max_length=1000, null=False, blank=False)

    def __str__(self):
        return self.subject

    class Meta:
        ordering = ("firstmessage",)


class MailThreadAttachment(models.Model):
    mailthread = models.ForeignKey(
        MailThread, null=False, blank=False, on_delete=models.CASCADE
    )
    messageid = models.CharField(max_length=1000, null=False, blank=False)
    attachmentid = models.IntegerField(null=False, blank=False)
    filename = models.CharField(max_length=1000, null=False, blank=True)
    date = models.DateTimeField(null=False, blank=False)
    author = models.CharField(max_length=500, null=False, blank=False)
    ispatch = models.BooleanField(null=True)

    class Meta:
        ordering = ("-date",)
        unique_together = (
            (
                "mailthread",
                "messageid",
            ),
        )


class MailThreadAnnotation(models.Model):
    mailthread = models.ForeignKey(
        MailThread, null=False, blank=False, on_delete=models.CASCADE
    )
    date = models.DateTimeField(null=False, blank=False, auto_now_add=True)
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)
    msgid = models.CharField(max_length=1000, null=False, blank=False)
    annotationtext = models.TextField(null=False, blank=False, max_length=2000)
    mailsubject = models.CharField(max_length=500, null=False, blank=False)
    maildate = models.DateTimeField(null=False, blank=False)
    mailauthor = models.CharField(max_length=500, null=False, blank=False)

    @property
    def user_string(self):
        return "%s %s (%s)" % (
            self.user.first_name,
            self.user.last_name,
            self.user.username,
        )

    class Meta:
        ordering = ("date",)


class PatchStatus(models.Model):
    status = models.IntegerField(null=False, blank=False, primary_key=True)
    statusstring = models.TextField(max_length=50, null=False, blank=False)
    sortkey = models.IntegerField(null=False, blank=False, default=10)


class PendingNotification(models.Model):
    history = models.ForeignKey(
        PatchHistory, blank=False, null=False, on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, blank=False, null=False, on_delete=models.CASCADE)


class CfbotBranch(models.Model):
    STATUS_CHOICES = [
        ("testing", "Testing"),
        ("finished", "Finished"),
        ("failed", "Failed"),
        ("timeout", "Timeout"),
    ]

    patch = models.OneToOneField(
        Patch, on_delete=models.CASCADE, related_name="cfbot_branch", primary_key=True
    )
    branch_id = models.IntegerField(null=False)
    branch_name = models.TextField(null=False)
    commit_id = models.TextField(null=True, blank=True)
    apply_url = models.TextField(null=False)
    # Actually a postgres enum column
    status = models.TextField(choices=STATUS_CHOICES, null=False)
    needs_rebase_since = models.DateTimeField(null=True, blank=True)
    failing_since = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    version = models.TextField(null=True, blank=True)
    patch_count = models.IntegerField(null=True, blank=True)
    first_additions = models.IntegerField(null=True, blank=True)
    first_deletions = models.IntegerField(null=True, blank=True)
    all_additions = models.IntegerField(null=True, blank=True)
    all_deletions = models.IntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """Only used by the admin panel to save empty commit id as NULL

        The actual cfbot webhook doesn't use the django ORM to save the data.
        """

        if not self.commit_id:
            self.commit_id = None
        super(CfbotBranch, self).save(*args, **kwargs)


class CfbotTask(models.Model):
    STATUS_CHOICES = [
        ("CREATED", "Created"),
        ("NEEDS_APPROVAL", "Needs Approval"),
        ("TRIGGERED", "Triggered"),
        ("EXECUTING", "Executing"),
        ("FAILED", "Failed"),
        ("COMPLETED", "Completed"),
        ("SCHEDULED", "Scheduled"),
        ("ABORTED", "Aborted"),
        ("ERRORED", "Errored"),
    ]

    # This id is only used by Django. Using text type for primary keys, has
    # historically caused problems.
    id = models.BigAutoField(primary_key=True)
    # This is the id used by the external CI system. Currently with CirrusCI
    # this is an integer, and thus we could probably store it as such. But
    # given that we might need to change CI providers at some point, and that
    # CI provider might use e.g. UUIDs, we prefer to consider the format of the
    # ID opaque and store it as text.
    task_id = models.TextField(unique=True)
    task_name = models.TextField(null=False)
    patch = models.ForeignKey(
        Patch, on_delete=models.CASCADE, related_name="cfbot_tasks"
    )
    branch_id = models.IntegerField(null=False)
    position = models.IntegerField(null=False)
    # Actually a postgres enum column
    status = models.TextField(choices=STATUS_CHOICES, null=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)


# Workflow provides access to the elements required to support
# the workflow this application is built for.  These elements exist
# independent of what the user is presently seeing on their page.
class Workflow(models.Model):
    def get_poc_for_patchid_or_404(patchid):
        return get_object_or_404(
            Patch.objects.select_related(), pk=patchid
        ).current_patch_on_commitfest()

    # At most a single Open CommitFest is allowed and this function returns it.
    def open_cf():
        cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_OPEN))
        return cfs[0] if len(cfs) == 1 else None

    # At most a single In Progress CommitFest is allowed and this function returns it.
    def inprogress_cf():
        cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_INPROGRESS))
        return cfs[0] if len(cfs) == 1 else None

    # At most a single Parked CommitFest is allowed and this function returns it.
    def parked_cf():
        cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_PARKED))
        return cfs[0] if len(cfs) == 1 else None

    # Returns whether the user is a committer in general and for this patch
    # since we retrieve all committers in order to answer these questions
    # provide that list as a third return value.  Passing None for both user
    # and patch still returns the list of committers.
    def isCommitter(user, patch):
        all_committers = Committer.objects.filter(active=True).order_by(
            "user__last_name", "user__first_name"
        )
        if not user and not patch:
            return False, False, all_committers

        committer = [c for c in all_committers if c.user == user]
        if len(committer) == 1:
            is_committer = True
            is_this_committer = committer[0] == patch.committer
        else:
            is_committer = is_this_committer = False
        return is_committer, is_this_committer, all_committers

    def getCommitfest(cfid):
        if cfid is None or cfid == "":
            return None
        try:
            int_cfid = int(cfid)
            cfs = list(CommitFest.objects.filter(id=int_cfid))
            if len(cfs) == 1:
                return cfs[0]
            else:
                return None
        except ValueError:
            return None

    # Implements a re-entrant Commitfest POC creation procedure.
    # Returns the new POC object.
    # Creates history and notifies as a side-effect.
    def createNewPOC(patch, commitfest, initial_status, by_user):
        poc, created = PatchOnCommitFest.objects.update_or_create(
            patch=patch,
            commitfest=commitfest,
            defaults=dict(
                enterdate=datetime.now(),
                status=initial_status,
                leavedate=None,
            ),
        )
        poc.patch.set_modified()
        poc.patch.save()
        poc.save()

        PatchHistory(
            patch=poc.patch,
            by=by_user,
            what="{} in {}".format(poc.statusstring, commitfest.name),
        ).save_and_notify()

        return poc

    # The rule surrounding patches is they may only be in one active
    # commitfest at a time.  The transition function takes a patch
    # open in one commitfest and associates it, with the same status,
    # in a new commitfest; then makes it inactive in the original.
    # Returns the new POC object.
    # Creates history and notifies as a side-effect.
    def transitionPatch(poc, target_cf, by_user):
        Workflow.userCanTransitionPatch(poc, target_cf, by_user)

        existing_status = poc.status

        # History looks cleaner if we've left the existing
        # commitfest entry before joining the new one.  Plus,
        # not allowed to change non-current commitfest status
        # and once the new POC is created it becomes current.

        Workflow.updatePOCStatus(poc, PatchOnCommitFest.STATUS_NEXT, by_user)

        new_poc = Workflow.createNewPOC(poc.patch, target_cf, existing_status, by_user)

        return new_poc

    def userCanTransitionPatch(poc, target_cf, user):
        # Policies not allowed to be broken by anyone.

        # Prevent changes to non-current commitfest for the patch
        # Meaning, status changed to Moved before/during transitioning
        # i.e., a concurrent action took place.
        if poc.commitfest != poc.patch.current_commitfest():
            raise Exception("Patch commitfest is not its current commitfest.")

        # The UI should be preventing people from trying to perform no-op requests
        if poc.commitfest.id == target_cf.id:
            raise Exception("Cannot transition to the same commitfest.")

        # This one is arguable but facilitates treating non-open status as final
        # A determined staff member can always change the status first.
        if poc.is_closed:
            raise Exception("Cannot transition a closed patch.")

        # We trust privileged users to make informed choices
        if user.is_staff:
            return

        if target_cf.isclosed:
            raise Exception("Cannot transition to a closed commitfest.")

        if target_cf.isinprogress:
            raise Exception("Cannot transition to an in-progress commitfest.")

        # Prevent users from moving closed patches, or moving open ones to
        # non-open commitfests.  The else clause should be a can't happen.
        if poc.is_open and target_cf.isopen:
            pass
        else:
            # Default deny policy basis
            raise Exception("Transition not permitted.")

    def userCanChangePOCStatus(poc, new_status, user):
        # Policies not allowed to be broken by anyone.

        # Prevent changes to non-current commitfest for the patch
        # Meaning, change status to Moved before/during transitioning
        if poc.commitfest != poc.patch.current_commitfest():
            raise Exception("Patch commitfest is not its current commitfest.")

        # The UI should be preventing people from trying to perform no-op requests
        if poc.status == new_status:
            raise Exception("Cannot change to the same status.")

        # We want commits to happen from, usually, In Progress commitfests,
        # or Open ones for exempt patches.  We accept Future ones too just because
        # they do represent a proper, if non-current, Commitfest.
        if (
            poc.commitfest.id == CommitFest.STATUS_PARKED
            and new_status == PatchOnCommitFest.STATUS_COMMITTED
        ):
            raise Exception("Cannot change status to committed in a parked commitfest.")

        # We trust privileged users to make informed choices
        if user.is_staff:
            return

        is_committer, is_this_committer, all_committers = Workflow.isCommitter(
            user, poc.patch
        )

        # XXX Not sure if we want to tighten this up to is_this_committer
        # with only the is_staff exemption
        if new_status == PatchOnCommitFest.STATUS_COMMITTED and not is_committer:
            raise Exception("Only a committer can set status to committed.")

        if new_status == PatchOnCommitFest.STATUS_REJECTED and not is_committer:
            raise Exception("Only a committer can set status to rejected.")

        if new_status == PatchOnCommitFest.STATUS_RETURNED and not is_committer:
            raise Exception("Only a committer can set status to returned.")

        if (
            new_status == PatchOnCommitFest.STATUS_WITHDRAWN
            and user not in poc.patch.authors.all()
        ):
            raise Exception("Only the author can set status to withdrawn.")

        # Prevent users from modifying closed patches
        # The else clause should be considered a can't happen
        if poc.is_open:
            pass
        else:
            raise Exception("Cannot change status of closed patch.")

    # Update the status of a PoC
    # Returns True if the status was changed, False for a same-status no-op.
    # Creates history and notifies as a side-effect.
    def updatePOCStatus(poc, new_status, by_user):
        # XXX Workflow disallows this no-op but not quite ready to enforce it.
        if poc.status == new_status:
            return False

        Workflow.userCanChangePOCStatus(poc, new_status, by_user)

        poc.status = new_status
        poc.leavedate = datetime.now() if not poc.is_open else None
        poc.patch.set_modified()
        poc.patch.save()
        poc.save()
        PatchHistory(
            patch=poc.patch,
            by=by_user,
            what="{} in {}".format(
                poc.statusstring,
                poc.commitfest.name,
            ),
        ).save_and_notify()

        return True
