# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('commitfest', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingNotification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('history', models.ForeignKey(to='commitfest.PatchHistory')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='patch',
            name='subscribers',
            field=models.ManyToManyField(related_name='patch_subscriber', to=settings.AUTH_USER_MODEL, blank=True),
        ),
    ]
