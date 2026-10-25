from datetime import datetime
from email import message_from_string

import pytest

from pgcommitfest.commitfest.models import MailThread, Patch, PatchOnCommitFest
from pgcommitfest.mailqueue.models import QueuedMail

pytestmark = pytest.mark.django_db


@pytest.fixture
def patch_with_thread(open_cf, alice, bob):
    patch = Patch.objects.create(name="Test patch")
    patch.authors.add(alice)
    patch.reviewers.add(bob)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=open_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )
    thread = MailThread.objects.create(
        messageid="first@example.com",
        subject="[PATCH] Test",
        firstmessage=datetime(2025, 1, 1),
        firstauthor="Alice <alice@example.com>",
        latestmessage=datetime(2025, 1, 2),
        latestauthor="Bob <bob@example.com>",
        latestsubject="Re: [PATCH] Test",
        latestmsgid="latest@example.com",
    )
    patch.mailthread_set.add(thread)
    return patch


@pytest.mark.parametrize("what", ["comment", "review"])
def test_reply_page_links_to_archives(
    client, patch_with_thread, in_progress_cf, recent_closed_cf, what
):
    response = client.get(f"/patch/{patch_with_thread.id}/{what}/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "https://www.postgresql.org/message-id/latest@example.com" in content
    assert "Resend email" in content
    assert ("make installcheck-world" in content) == (what == "review")
    assert not QueuedMail.objects.exists()


def test_staff_email_not_sent_from_manager_address(
    client, patch_with_thread, alice, bob, charlie, settings
):
    charlie.is_staff = True
    charlie.save()
    client.force_login(charlie)

    response = client.post(
        f"/patch/{patch_with_thread.id}/send_email/",
        {
            "authors": str(patch_with_thread.id),
            "reviewers": str(patch_with_thread.id),
            "subject": "Hello",
            "body": "Please rebase",
            "confirm": "on",
        },
    )
    assert response.status_code == 302

    mails = list(QueuedMail.objects.order_by("receiver"))
    assert [m.receiver for m in mails] == ["alice@example.com", "bob@example.com"]
    for m in mails:
        assert m.sender == settings.NOTIFICATION_FROM
        msg = message_from_string(m.fullmsg)
        assert msg["From"] == (
            f"Charlie Chen via PostgreSQL Commitfest <{settings.NOTIFICATION_FROM}>"
        )
        assert msg["Reply-To"] == "Charlie Chen <charlie@example.com>"
