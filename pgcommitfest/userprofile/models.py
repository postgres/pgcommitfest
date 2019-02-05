from django.db import models
from django.contrib.auth.models import User

class UserExtraEmail(models.Model):
    user = models.ForeignKey(User, null=False, blank=False, db_index=True)
    email = models.EmailField(max_length=100, null=False, blank=False, unique=True)
    confirmed = models.BooleanField(null=False, blank=False, default=False)
    token = models.CharField(max_length=100, null=False, blank=True)
    tokensent = models.DateTimeField(null=False, blank=False)

    def __unicode__(self):
        return self.email

    class Meta:
        ordering = ('user', 'email')
        unique_together = (('user', 'email'),)


class UserProfile(models.Model):
    user = models.OneToOneField(User, null=False, blank=False)
    selectedemail = models.ForeignKey(UserExtraEmail, null=True, blank=True,
                                      verbose_name='Sender email')
    notifyemail = models.ForeignKey(UserExtraEmail, null=True, blank=True,
                                    verbose_name='Notifications sent to',
                                    related_name='notifier')
    notify_all_author = models.BooleanField(null=False, blank=False, default=False, verbose_name="Notify on all where author")
    notify_all_reviewer = models.BooleanField(null=False, blank=False, default=False, verbose_name="Notify on all where reviewer")
    notify_all_committer = models.BooleanField(null=False, blank=False, default=False, verbose_name="Notify on all where committer")

    def __unicode__(self):
        return unicode(self.user)
