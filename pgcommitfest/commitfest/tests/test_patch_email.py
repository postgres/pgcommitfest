from datetime import datetime
from email import message_from_string

import pytest

from pgcommitfest.commitfest.models import Patch, PatchOnCommitFest
from pgcommitfest.mailqueue.models import QueuedMail

pytestmark = pytest.mark.django_db


def test_staff_email_not_sent_from_manager_address(
    client, open_cf, alice, charlie, settings
):
    patch = Patch.objects.create(name="Test patch")
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch, commitfest=open_cf, enterdate=datetime.now()
    )
    charlie.is_staff = True
    charlie.save()
    client.force_login(charlie)

    client.post(
        f"/patch/{patch.id}/send_email/",
        {
            "authors": patch.id,
            "reviewers": "",
            "subject": "Hi",
            "body": "Rebase",
            "confirm": "on",
        },
    )

    mail = QueuedMail.objects.get()
    msg = message_from_string(mail.fullmsg)
    assert mail.sender == settings.NOTIFICATION_FROM
    assert msg["Reply-To"] == "Charlie Chen <charlie@example.com>"
