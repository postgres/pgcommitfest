from datetime import datetime
from unittest.mock import patch

import pytest

from pgcommitfest.commitfest.ajax import refresh_single_thread
from pgcommitfest.commitfest.models import MailThread, MailThreadAttachment, Patch

pytestmark = pytest.mark.django_db


def test_refresh_single_thread():
    """A new mail updates patch.lastmail and refreshes stale attachment info."""
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
    attachment = MailThreadAttachment.objects.create(
        mailthread=thread,
        messageid="old@example.com",
        attachmentid=1,
        filename="old.patch",
        date=old_date,
        author="a",
    )

    api_response = [
        {
            "msgid": "old@example.com",
            "date": old_date,
            "from": "a",
            "subj": "T",
            # The archives assigned a new id to the same attachment
            "atts": [{"id": 2, "name": "new.patch"}],
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
    attachment.refresh_from_db()
    assert (attachment.attachmentid, attachment.filename) == (2, "new.patch")
    assert MailThreadAttachment.objects.filter(mailthread=thread).count() == 1
