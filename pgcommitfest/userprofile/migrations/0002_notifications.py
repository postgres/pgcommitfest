# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ("userprofile", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="notify_all_author",
            field=models.BooleanField(
                default=False, verbose_name="Notify on all where author"
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="notify_all_committer",
            field=models.BooleanField(
                default=False, verbose_name="Notify on all where committer"
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="notify_all_reviewer",
            field=models.BooleanField(
                default=False, verbose_name="Notify on all where reviewer"
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="notifyemail",
            field=models.ForeignKey(
                related_name="notifier",
                verbose_name="Notifications sent to",
                blank=True,
                to="userprofile.UserExtraEmail",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="user",
            field=models.OneToOneField(
                to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE
            ),
        ),
    ]
