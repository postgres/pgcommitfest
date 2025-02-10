from django.db import models
from django.contrib.auth.models import User


class UserExtraEmail(models.Model):
    user = models.ForeignKey(
        User, null=False, blank=False, db_index=True, on_delete=models.CASCADE
    )
    email = models.EmailField(max_length=100, null=False, blank=False, unique=True)

    def __str__(self):
        return self.email

    class Meta:
        ordering = ("user", "email")
        unique_together = (("user", "email"),)


class UserProfile(models.Model):
    user = models.OneToOneField(User, null=False, blank=False, on_delete=models.CASCADE)
    selectedemail = models.ForeignKey(
        UserExtraEmail,
        null=True,
        blank=True,
        verbose_name="Sender email",
        on_delete=models.SET_NULL,
    )
    notifyemail = models.ForeignKey(
        UserExtraEmail,
        null=True,
        blank=True,
        verbose_name="Notifications sent to",
        related_name="notifier",
        on_delete=models.SET_NULL,
    )
    notify_all_author = models.BooleanField(
        null=False,
        blank=False,
        default=False,
        verbose_name="Notify on all where author",
    )
    notify_all_reviewer = models.BooleanField(
        null=False,
        blank=False,
        default=False,
        verbose_name="Notify on all where reviewer",
    )
    notify_all_committer = models.BooleanField(
        null=False,
        blank=False,
        default=False,
        verbose_name="Notify on all where committer",
    )

    def __str__(self):
        return str(self.user)
