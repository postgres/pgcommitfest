from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from datetime import datetime, timedelta, timezone

from pgcommitfest.mailqueue.util import send_template_mail
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
    STATUS_OPEN = 2
    STATUS_INPROGRESS = 3
    STATUS_CLOSED = 4
    _STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_INPROGRESS, "In Progress"),
        (STATUS_CLOSED, "Closed"),
    )
    _STATUS_LABELS = (
        (STATUS_OPEN, "info"),
        (STATUS_INPROGRESS, "success"),
        (STATUS_CLOSED, "danger"),
    )
    name = models.CharField(max_length=100, blank=False, null=False, unique=True)
    status = models.IntegerField(
        null=False, blank=False, default=2, choices=_STATUS_CHOICES
    )
    startdate = models.DateField(blank=False, null=False)
    enddate = models.DateField(blank=False, null=False)
    draft = models.BooleanField(blank=False, null=False, default=False)

    @property
    def statusstring(self):
        return [v for k, v in self._STATUS_CHOICES if k == self.status][0]

    @property
    def periodstring(self):
        return "{0} – {1}".format(self.startdate, self.enddate)

    @property
    def last_open_date(self):
        return self.startdate - timedelta(days=1)

    @property
    def dev_cycle(self) -> int:
        if self.startdate.month in [1, 3]:
            return self.startdate.year - 2007
        else:
            return self.startdate.year - 2006

    @property
    def title(self):
        return "Commitfest %s" % self.name

    @property
    def is_closed(self):
        return self.status == self.STATUS_CLOSED

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN

    @property
    def is_open_regular(self):
        return self.is_open and not self.draft

    @property
    def is_open_draft(self):
        return self.is_open and self.draft

    @property
    def is_in_progress(self):
        return self.status == self.STATUS_INPROGRESS

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.statusstring,
            "startdate": self.startdate.isoformat(),
            "enddate": self.enddate.isoformat(),
        }

    def _should_auto_move_patch(self, patch, current_date):
        """Determine if a patch should be automatically moved to the next commitfest.

        A patch qualifies for auto-move if it both:
        1. Has had email activity within the configured number of days
        2. Hasn't been failing CI for longer than the configured threshold
        """
        activity_cutoff = current_date - timedelta(
            days=settings.AUTO_MOVE_EMAIL_ACTIVITY_DAYS
        )
        failing_cutoff = current_date - timedelta(
            days=settings.AUTO_MOVE_MAX_FAILING_DAYS
        )

        # Check for recent email activity
        if not patch.lastmail or patch.lastmail < activity_cutoff:
            return False

        # Check if CI has been failing too long
        try:
            cfbot_branch = patch.cfbot_branch
            if (
                cfbot_branch.failing_since
                and cfbot_branch.failing_since < failing_cutoff
            ):
                return False
        except CfbotBranch.DoesNotExist:
            pass

        return True

    def auto_move_active_patches(self):
        """Automatically move active patches to the next commitfest.

        A patch is moved if it has recent email activity and hasn't been
        failing CI for too long.

        Returns a set of patch IDs that were moved.
        """
        current_date = datetime.now()

        # Get the next open commitfest
        # For draft CFs, find the next draft CF
        # For regular CFs, find the next regular CF by start date
        if self.draft:
            next_cf = (
                CommitFest.objects.filter(
                    status=CommitFest.STATUS_OPEN,
                    draft=True,
                    startdate__gt=self.enddate,
                )
                .order_by("startdate")
                .first()
            )
        else:
            next_cf = (
                CommitFest.objects.filter(
                    status=CommitFest.STATUS_OPEN,
                    draft=False,
                    startdate__gt=self.enddate,
                )
                .order_by("startdate")
                .first()
            )

        if not next_cf:
            return set()

        # Get all patches with open status in this commitfest
        open_pocs = self.patchoncommitfest_set.filter(
            status__in=[
                PatchOnCommitFest.STATUS_REVIEW,
                PatchOnCommitFest.STATUS_AUTHOR,
                PatchOnCommitFest.STATUS_COMMITTER,
            ]
        ).select_related("patch")

        moved_patch_ids = set()
        for poc in open_pocs:
            if self._should_auto_move_patch(poc.patch, current_date):
                poc.patch.move(self, next_cf, by_user=None, by_cfbot=True)
                moved_patch_ids.add(poc.patch.id)

        return moved_patch_ids

    def send_closure_notifications(self, moved_patch_ids=None):
        """Send email notifications to authors of patches that weren't auto-moved.

        Args:
            moved_patch_ids: Set of patch IDs that were auto-moved to the next commitfest.
                           These patches are excluded since the move triggers its own notification.
        """
        if moved_patch_ids is None:
            moved_patch_ids = set()

        # Get patches that still need action (not moved, not closed)
        open_pocs = list(
            self.patchoncommitfest_set.filter(
                status__in=[
                    PatchOnCommitFest.STATUS_REVIEW,
                    PatchOnCommitFest.STATUS_AUTHOR,
                    PatchOnCommitFest.STATUS_COMMITTER,
                ]
            )
            .exclude(patch_id__in=moved_patch_ids)
            .select_related("patch")
            .prefetch_related("patch__authors")
        )

        if not open_pocs:
            return

        # Get the next open commitfest if available
        next_cf = (
            CommitFest.objects.filter(
                status=CommitFest.STATUS_OPEN,
                draft=self.draft,
                startdate__gt=self.enddate,
            )
            .order_by("startdate")
            .first()
        )

        if next_cf:
            next_cf_url = f"https://commitfest.postgresql.org/{next_cf.id}/"
        else:
            next_cf_url = "https://commitfest.postgresql.org/"

        # Collect unique authors and their patches
        authors_patches = {}
        for poc in open_pocs:
            for author in poc.patch.authors.all():
                if not author.email:
                    continue
                if author not in authors_patches:
                    authors_patches[author] = []
                authors_patches[author].append(poc)

        # Send email to each author
        for author, patches in authors_patches.items():
            # Get user's notification email preference
            email = author.email
            try:
                if author.userprofile and author.userprofile.notifyemail:
                    email = author.userprofile.notifyemail.email
            except UserProfile.DoesNotExist:
                pass

            send_template_mail(
                settings.NOTIFICATION_FROM,
                None,
                email,
                f"Commitfest {self.name} has closed",
                "mail/commitfest_closure.txt",
                {
                    "user": author,
                    "commitfest": self,
                    "patches": patches,
                    "next_cf": next_cf,
                    "next_cf_url": next_cf_url,
                },
            )

    @staticmethod
    def _are_relevant_commitfests_up_to_date(cfs, current_date):
        inprogress_cf = cfs["in_progress"]

        if inprogress_cf and inprogress_cf.enddate < current_date:
            return False

        if cfs["open"].startdate <= current_date:
            return False

        if not cfs["draft"] or cfs["draft"].enddate < current_date:
            return False

        return True

    @classmethod
    def _refresh_relevant_commitfests(cls, for_update):
        cfs = CommitFest.relevant_commitfests(for_update=for_update, refresh=False)
        current_date = datetime.now(timezone.utc).date()

        if cls._are_relevant_commitfests_up_to_date(cfs, current_date):
            return cfs

        with transaction.atomic():
            cfs = CommitFest.relevant_commitfests(for_update=True, refresh=False)
            if cls._are_relevant_commitfests_up_to_date(cfs, current_date):
                # Some other request has already updated the commitfests, so we
                # return the new version
                return cfs

            inprogress_cf = cfs["in_progress"]
            if inprogress_cf and inprogress_cf.enddate < current_date:
                moved_patch_ids = inprogress_cf.auto_move_active_patches()
                inprogress_cf.status = CommitFest.STATUS_CLOSED
                inprogress_cf.save()
                inprogress_cf.send_closure_notifications(moved_patch_ids)

            open_cf = cfs["open"]

            if open_cf.startdate <= current_date:
                if open_cf.enddate < current_date:
                    moved_patch_ids = open_cf.auto_move_active_patches()
                    open_cf.status = CommitFest.STATUS_CLOSED
                    open_cf.save()
                    open_cf.send_closure_notifications(moved_patch_ids)
                else:
                    open_cf.status = CommitFest.STATUS_INPROGRESS
                    open_cf.save()

                cls.next_open_cf(current_date).save()

            draft_cf = cfs["draft"]
            if not draft_cf:
                cls.next_draft_cf(current_date).save()
            elif draft_cf.enddate < current_date:
                # If the draft commitfest has started, we need to update it
                moved_patch_ids = draft_cf.auto_move_active_patches()
                draft_cf.status = CommitFest.STATUS_CLOSED
                draft_cf.save()
                draft_cf.send_closure_notifications(moved_patch_ids)
                cls.next_draft_cf(current_date).save()

            return cls.relevant_commitfests(for_update=for_update)

    @classmethod
    def relevant_commitfests(cls, for_update=False, refresh=True):
        """If refresh is True (which is the default) this will automatically
        update the commitfests if their state is out of date. It will also
        create a new ones automatically when needed.

        The primary reason this refreshing is not done through a cron job is
        that that requires work on the infrastructure side. Which is a huge
        hassle to make happen in practice, due to an overloaded infrastructure
        team.

        Luckily checking if a refresh is needed is very cheap, just a few
        comparisons (see _are_relevant_commitfests_up_to_date for details). And
        the actual updates only happen ~once a month.
        """
        if refresh and settings.AUTO_CREATE_COMMITFESTS:
            return cls._refresh_relevant_commitfests(for_update=for_update)

        query_base = CommitFest.objects.order_by("-enddate")
        if for_update:
            query_base = query_base.select_for_update(no_key=True)
        last_three_commitfests = query_base.filter(draft=False)[:3]

        cfs = {}
        cfs["open"] = last_three_commitfests[0]

        if last_three_commitfests[1].status == CommitFest.STATUS_INPROGRESS:
            cfs["in_progress"] = last_three_commitfests[1]
            cfs["previous"] = last_three_commitfests[2]

        else:
            cfs["in_progress"] = None
            cfs["previous"] = last_three_commitfests[1]
            if cfs["open"].startdate.month == 3:
                cfs["final"] = cfs["open"]

        if cfs["in_progress"] and cfs["in_progress"].startdate.month == 3:
            cfs["final"] = cfs["in_progress"]
        elif cfs["open"].startdate.month == 3:
            cfs["final"] = cfs["open"]
        else:
            cfs["final"] = cls.next_open_cf(
                datetime(year=cfs["open"].dev_cycle + 2007, month=2, day=1)
            )

        cfs["draft"] = query_base.filter(draft=True).order_by("-startdate").first()
        cfs["next_open"] = cls.next_open_cf(cfs["open"].enddate + timedelta(days=1))

        return cfs

    @staticmethod
    def next_open_cf(from_date):
        # We don't have a CF in december, so we don't need to worry about 12 mod 12 being 0
        cf_months = [7, 9, 11, 1, 3]
        next_open_cf_month = min(
            (month for month in cf_months if month > from_date.month), default=1
        )
        next_open_cf_year = from_date.year
        if next_open_cf_month == 1:
            next_open_cf_year += 1

        next_open_dev_cycle = next_open_cf_year - 2006
        if next_open_cf_month in [1, 3]:
            next_open_dev_cycle -= 1

        if next_open_cf_month == 3:
            name = f"PG{next_open_dev_cycle}-Final"
        else:
            cf_number = cf_months.index(next_open_cf_month) + 1
            name = f"PG{next_open_dev_cycle}-{cf_number}"
        start_date = datetime(
            year=next_open_cf_year, month=next_open_cf_month, day=1
        ).date()
        end_date = datetime(
            year=next_open_cf_year, month=next_open_cf_month + 1, day=1
        ).date() - timedelta(days=1)

        return CommitFest(
            name=name,
            status=CommitFest.STATUS_OPEN,
            startdate=start_date,
            enddate=end_date,
        )

    @staticmethod
    def next_draft_cf(start_date):
        dev_cycle = start_date.year - 2006
        if start_date.month < 3:
            dev_cycle -= 1

        end_year = dev_cycle + 2007

        name = f"PG{dev_cycle}-Drafts"
        end_date = datetime(year=end_year, month=3, day=1).date() - timedelta(days=1)

        return CommitFest(
            name=name,
            status=CommitFest.STATUS_OPEN,
            startdate=start_date,
            enddate=end_date,
            draft=True,
        )

    @classmethod
    def get_in_progress(cls):
        return cls.objects.filter(status=CommitFest.STATUS_INPROGRESS).first()

    @classmethod
    def get_open_regular(cls):
        return cls.objects.filter(status=CommitFest.STATUS_OPEN, draft=False).first()

    @classmethod
    def get_current(cls):
        # First try to get in-progress CommitFest
        current = cls.get_in_progress()
        if current:
            return current
        # If no in-progress, fall back to open regular CommitFest
        return cls.get_open_regular()

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


class ColorField(models.CharField):
    """
    A small wrapper around a CharField that can hold a #RRGGBB color code. The
    primary reason to have this wrapper class is so that the TagAdmin class can
    explicitly key off of it to inject a color picker in the admin interface.
    """

    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 7  # for `#RRGGBB` format
        super().__init__(*args, **kwargs)


class Tag(models.Model):
    """Represents a tag/label on a patch."""

    name = models.CharField(max_length=50, unique=True)
    color = ColorField()
    description = models.CharField(max_length=500)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class UserInputError(ValueError):
    pass


class Patch(models.Model, DiffableModel):
    name = models.CharField(
        max_length=500, blank=False, null=False, verbose_name="Description"
    )
    # Topic is deprecated, tags are used instead. For now this field is kept
    # for debugging purposes in case of problems with the migration.
    topic = models.ForeignKey(Topic, blank=True, null=True, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag, related_name="patches", blank=True)

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
            PatchOnCommitFest, Q(patch=self) & ~Q(status=PatchOnCommitFest.STATUS_MOVED)
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

    def move(
        self, from_cf, to_cf, by_user, allow_move_to_in_progress=False, by_cfbot=False
    ):
        """Returns the new PatchOnCommitFest object, or raises UserInputError"""

        current_poc = self.current_patch_on_commitfest()
        if from_cf.id != current_poc.commitfest.id:
            raise UserInputError("Patch not in source commitfest.")

        if from_cf.id == to_cf.id:
            raise UserInputError("Source and target commitfest are the same.")

        if current_poc.status not in (
            PatchOnCommitFest.STATUS_REVIEW,
            PatchOnCommitFest.STATUS_AUTHOR,
            PatchOnCommitFest.STATUS_COMMITTER,
        ):
            raise UserInputError(
                f"Patch in state {current_poc.statusstring} cannot be moved."
            )

        if to_cf.is_in_progress:
            if not allow_move_to_in_progress:
                raise UserInputError("Patch can only be moved to an open commitfest")
        elif not to_cf.is_open:
            raise UserInputError("Patch can only be moved to an open commitfest")

        old_status = current_poc.status

        current_poc.set_status(PatchOnCommitFest.STATUS_MOVED)

        new_poc, _ = PatchOnCommitFest.objects.update_or_create(
            patch=current_poc.patch,
            commitfest=to_cf,
            defaults=dict(
                status=old_status,
                enterdate=datetime.now(),
                leavedate=None,
            ),
        )
        new_poc.save()
        self.set_modified()
        self.save()

        PatchHistory(
            patch=self,
            by=by_user,
            by_cfbot=by_cfbot,
            what=f"Moved from CF {from_cf} to CF {to_cf}",
        ).save_and_notify()

        return new_poc

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
    STATUS_MOVED = 5
    STATUS_REJECTED = 6
    STATUS_RETURNED = 7
    STATUS_WITHDRAWN = 8
    _STATUS_CHOICES = (
        (STATUS_REVIEW, "Needs review"),
        (STATUS_AUTHOR, "Waiting on Author"),
        (STATUS_COMMITTER, "Ready for Committer"),
        (STATUS_COMMITTED, "Committed"),
        (STATUS_MOVED, "Moved to different CF"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_RETURNED, "Returned with feedback"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    )
    _STATUS_LABELS = (
        (STATUS_REVIEW, "secondary"),
        (STATUS_AUTHOR, "primary"),
        (STATUS_COMMITTER, "info"),
        (STATUS_COMMITTED, "success"),
        (STATUS_MOVED, "warning"),
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

    @classmethod
    def current_for_patch(cls, patch_id):
        return get_object_or_404(
            cls, Q(patch_id=patch_id) & ~Q(status=cls.STATUS_MOVED)
        )

    def set_status(self, status):
        self.status = status
        if not self.leavedate and not self.is_open:
            # If the patch was not closed before, we need to set the leavedate
            # now.
            self.leavedate = datetime.now()
        elif self.is_open:
            self.leavedate = None

        self.patch.set_modified()

        self.patch.save()
        self.save()

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
        ("PAUSED", "Paused"),
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
    task_id = models.TextField()
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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch_id", "position"],
                name="commitfest_cfbottask_branch_position_unique",
            )
        ]
