from datetime import datetime
from unittest.mock import patch

import pytest

from pgcommitfest.commitfest.ajax import refresh_single_thread
from pgcommitfest.commitfest.models import MailThread, Patch

pytestmark = pytest.mark.django_db


def test_refresh_single_thread_updates_patch_lastmail():
    """Regression test: patch.lastmail should get the new date, not the old one."""
    old_date = datetime(2024, 1, 1)
    new_date = datetime(2024, 6, 15)

    thread = MailThread.objects.create(
        messageid="old@example.com",
        subject="Test",
        firstmessage=old_date,
        firstauthor="a@example.com",
        latestmessage=old_date,
        latestauthor="a@example.com",
        latestsubject="Test",
        latestmsgid="old@example.com",
    )
    p = Patch.objects.create(name="Test Patch", lastmail=old_date)
    p.mailthread_set.add(thread)

    api_response = [
        {
            "msgid": "old@example.com",
            "date": old_date,
            "from": "a",
            "subj": "T",
            "atts": [],
        },
        {
            "msgid": "new@example.com",
            "date": new_date,
            "from": "b",
            "subj": "T",
            "atts": [],
        },
    ]

    with patch("pgcommitfest.commitfest.ajax._archivesAPI", return_value=api_response):
        refresh_single_thread(thread)

    p.refresh_from_db()
    assert p.lastmail == new_date
