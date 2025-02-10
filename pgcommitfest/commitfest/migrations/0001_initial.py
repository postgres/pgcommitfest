# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models

import pgcommitfest.commitfest.util


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0006_require_contenttypes_0002"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CommitFest",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(unique=True, max_length=100)),
                (
                    "status",
                    models.IntegerField(
                        default=1,
                        choices=[
                            (1, "Future"),
                            (2, "Open"),
                            (3, "In Progress"),
                            (4, "Closed"),
                        ],
                    ),
                ),
                ("startdate", models.DateField(null=True, blank=True)),
                ("enddate", models.DateField(null=True, blank=True)),
            ],
            options={
                "ordering": ("-startdate",),
                "verbose_name_plural": "Commitfests",
            },
        ),
        migrations.CreateModel(
            name="Committer",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        primary_key=True,
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                        on_delete=models.CASCADE,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ("user__last_name", "user__first_name"),
            },
        ),
        migrations.CreateModel(
            name="MailThread",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("messageid", models.CharField(unique=True, max_length=1000)),
                ("subject", models.CharField(max_length=500)),
                ("firstmessage", models.DateTimeField()),
                ("firstauthor", models.CharField(max_length=500)),
                ("latestmessage", models.DateTimeField()),
                ("latestauthor", models.CharField(max_length=500)),
                ("latestsubject", models.CharField(max_length=500)),
                ("latestmsgid", models.CharField(max_length=1000)),
            ],
            options={
                "ordering": ("firstmessage",),
            },
        ),
        migrations.CreateModel(
            name="MailThreadAnnotation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("date", models.DateTimeField(auto_now_add=True)),
                ("msgid", models.CharField(max_length=1000)),
                ("annotationtext", models.TextField(max_length=2000)),
                ("mailsubject", models.CharField(max_length=500)),
                ("maildate", models.DateTimeField()),
                ("mailauthor", models.CharField(max_length=500)),
                (
                    "mailthread",
                    models.ForeignKey(
                        to="commitfest.MailThread", on_delete=models.CASCADE
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE
                    ),
                ),
            ],
            options={
                "ordering": ("date",),
            },
        ),
        migrations.CreateModel(
            name="MailThreadAttachment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("messageid", models.CharField(max_length=1000)),
                ("attachmentid", models.IntegerField()),
                ("filename", models.CharField(max_length=1000, blank=True)),
                ("date", models.DateTimeField()),
                ("author", models.CharField(max_length=500)),
                ("ispatch", models.BooleanField(null=True)),
                (
                    "mailthread",
                    models.ForeignKey(
                        to="commitfest.MailThread", on_delete=models.CASCADE
                    ),
                ),
            ],
            options={
                "ordering": ("-date",),
            },
        ),
        migrations.CreateModel(
            name="Patch",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(max_length=500, verbose_name="Description")),
                ("wikilink", models.URLField(default="", null=False, blank=True)),
                ("gitlink", models.URLField(default="", null=False, blank=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("modified", models.DateTimeField()),
                ("lastmail", models.DateTimeField(null=True, blank=True)),
                (
                    "authors",
                    models.ManyToManyField(
                        related_name="patch_author",
                        to=settings.AUTH_USER_MODEL,
                        blank=True,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "patches",
            },
            bases=(models.Model, pgcommitfest.commitfest.util.DiffableModel),
        ),
        migrations.CreateModel(
            name="PatchHistory",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("date", models.DateTimeField(auto_now_add=True)),
                ("what", models.CharField(max_length=500)),
                (
                    "by",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE
                    ),
                ),
                (
                    "patch",
                    models.ForeignKey(to="commitfest.Patch", on_delete=models.CASCADE),
                ),
            ],
            options={
                "ordering": ("-date",),
            },
        ),
        migrations.CreateModel(
            name="PatchOnCommitFest",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("enterdate", models.DateTimeField()),
                ("leavedate", models.DateTimeField(null=True, blank=True)),
                (
                    "status",
                    models.IntegerField(
                        default=1,
                        choices=[
                            (1, "Needs review"),
                            (2, "Waiting on Author"),
                            (3, "Ready for Committer"),
                            (4, "Committed"),
                            (5, "Moved to next CF"),
                            (6, "Rejected"),
                            (7, "Returned with feedback"),
                        ],
                    ),
                ),
                (
                    "commitfest",
                    models.ForeignKey(
                        to="commitfest.CommitFest", on_delete=models.CASCADE
                    ),
                ),
                (
                    "patch",
                    models.ForeignKey(to="commitfest.Patch", on_delete=models.CASCADE),
                ),
            ],
            options={
                "ordering": ("-commitfest__startdate",),
            },
        ),
        migrations.CreateModel(
            name="PatchStatus",
            fields=[
                ("status", models.IntegerField(serialize=False, primary_key=True)),
                ("statusstring", models.TextField(max_length=50)),
                ("sortkey", models.IntegerField(default=10)),
            ],
        ),
        migrations.CreateModel(
            name="Topic",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("topic", models.CharField(max_length=100)),
            ],
        ),
        migrations.AddField(
            model_name="patch",
            name="commitfests",
            field=models.ManyToManyField(
                to="commitfest.CommitFest", through="commitfest.PatchOnCommitFest"
            ),
        ),
        migrations.AddField(
            model_name="patch",
            name="committer",
            field=models.ForeignKey(
                blank=True,
                to="commitfest.Committer",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="patch",
            name="reviewers",
            field=models.ManyToManyField(
                related_name="patch_reviewer", to=settings.AUTH_USER_MODEL, blank=True
            ),
        ),
        migrations.AddField(
            model_name="patch",
            name="topic",
            field=models.ForeignKey(to="commitfest.Topic", on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name="mailthread",
            name="patches",
            field=models.ManyToManyField(to="commitfest.Patch"),
        ),
        migrations.AlterUniqueTogether(
            name="patchoncommitfest",
            unique_together=set([("patch", "commitfest")]),
        ),
        migrations.AlterUniqueTogether(
            name="mailthreadattachment",
            unique_together=set([("mailthread", "messageid")]),
        ),
    ]
