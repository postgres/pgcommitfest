# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commitfest", "0002_notifications"),
    ]

    operations = [
        migrations.AlterField(
            model_name="patchoncommitfest",
            name="status",
            field=models.IntegerField(
                default=1,
                choices=[
                    (1, "Needs review"),
                    (2, "Waiting on Author"),
                    (3, "Ready for Committer"),
                    (4, "Committed"),
                    (5, "Moved to next CF"),
                    (6, "Rejected"),
                    (7, "Returned with feedback"),
                    (8, "Withdrawn"),
                ],
            ),
        ),
        migrations.RunSQL("""
INSERT INTO commitfest_patchstatus (status, statusstring, sortkey) VALUES
(1,'Needs review',10),
(2,'Waiting on Author',15),
(3,'Ready for Committer',20),
(4,'Committed',25),
(5,'Moved to next CF',30),
(6,'Rejected',50),
(7,'Returned with Feedback',50),
(8,'Withdrawn', 50)
ON CONFLICT (status) DO UPDATE SET statusstring=excluded.statusstring, sortkey=excluded.sortkey;
"""),
        migrations.RunSQL(
            "DELETE FROM commitfest_patchstatus WHERE status < 1 OR status > 8"
        ),
    ]
