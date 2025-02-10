# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserExtraEmail",
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
                ("email", models.EmailField(unique=True, max_length=100)),
                ("confirmed", models.BooleanField(default=False)),
                ("token", models.CharField(max_length=100, blank=True)),
                ("tokensent", models.DateTimeField()),
                (
                    "user",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE
                    ),
                ),
            ],
            options={
                "ordering": ("user", "email"),
            },
        ),
        migrations.CreateModel(
            name="UserProfile",
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
                (
                    "selectedemail",
                    models.ForeignKey(
                        verbose_name="Sender email",
                        blank=True,
                        to="userprofile.UserExtraEmail",
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="userextraemail",
            unique_together=set([("user", "email")]),
        ),
    ]
