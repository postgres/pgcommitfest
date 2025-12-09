import base64
from datetime import datetime
from email import message_from_string

import pytest

from pgcommitfest.commitfest.models import Patch, PatchOnCommitFest, Topic
from pgcommitfest.mailqueue.models import QueuedMail

pytestmark = pytest.mark.django_db


def get_email_body(queued_mail):
    """Extract and decode the email body from a QueuedMail object."""
    msg = message_from_string(queued_mail.fullmsg)
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload()
            return base64.b64decode(payload).decode("utf-8")
    return ""


@pytest.fixture
def topic():
    """Create a test topic."""
    return Topic.objects.create(topic="General")


def test_send_closure_notifications_to_authors_of_open_patches(
    alice, in_progress_cf, topic
):
    """Authors of patches with open status should receive closure notifications."""
    patch = Patch.objects.create(name="Test Patch", topic=topic)
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    in_progress_cf.send_closure_notifications()

    assert QueuedMail.objects.count() == 1
    mail = QueuedMail.objects.first()
    assert mail.receiver == alice.email
    assert f"Commitfest {in_progress_cf.name} has closed" in mail.fullmsg
    body = get_email_body(mail)
    assert "Test Patch" in body


def test_no_notification_for_committed_patches(alice, in_progress_cf, topic):
    """Authors of committed patches should not receive notifications."""
    patch = Patch.objects.create(name="Committed Patch", topic=topic)
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        leavedate=datetime.now(),
        status=PatchOnCommitFest.STATUS_COMMITTED,
    )

    in_progress_cf.send_closure_notifications()

    assert QueuedMail.objects.count() == 0


def test_no_notification_for_withdrawn_patches(alice, in_progress_cf, topic):
    """Authors of withdrawn patches should not receive notifications."""
    patch = Patch.objects.create(name="Withdrawn Patch", topic=topic)
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        leavedate=datetime.now(),
        status=PatchOnCommitFest.STATUS_WITHDRAWN,
    )

    in_progress_cf.send_closure_notifications()

    assert QueuedMail.objects.count() == 0


def test_one_email_per_author_with_multiple_patches(alice, in_progress_cf, topic):
    """An author with multiple open patches should receive one email listing all patches."""
    patch1 = Patch.objects.create(name="Patch One", topic=topic)
    patch1.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch1,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    patch2 = Patch.objects.create(name="Patch Two", topic=topic)
    patch2.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch2,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_AUTHOR,
    )

    in_progress_cf.send_closure_notifications()

    assert QueuedMail.objects.count() == 1
    mail = QueuedMail.objects.first()
    body = get_email_body(mail)
    assert "Patch One" in body
    assert "Patch Two" in body


def test_multiple_authors_receive_separate_emails(alice, bob, in_progress_cf, topic):
    """Each author of open patches should receive their own notification."""
    patch1 = Patch.objects.create(name="Alice Patch", topic=topic)
    patch1.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch1,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    patch2 = Patch.objects.create(name="Bob Patch", topic=topic)
    patch2.authors.add(bob)
    PatchOnCommitFest.objects.create(
        patch=patch2,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_COMMITTER,
    )

    in_progress_cf.send_closure_notifications()

    assert QueuedMail.objects.count() == 2
    receivers = set(QueuedMail.objects.values_list("receiver", flat=True))
    assert receivers == {alice.email, bob.email}


def test_notification_includes_next_commitfest_info(alice, in_progress_cf, open_cf, topic):
    """Notification should include information about the next open commitfest."""
    patch = Patch.objects.create(name="Test Patch", topic=topic)
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    in_progress_cf.send_closure_notifications()

    mail = QueuedMail.objects.first()
    body = get_email_body(mail)
    assert open_cf.name in body
    assert f"https://commitfest.postgresql.org/{open_cf.id}/" in body


def test_coauthors_both_receive_notification(alice, bob, in_progress_cf, topic):
    """Both co-authors of a patch should receive notifications."""
    patch = Patch.objects.create(name="Coauthored Patch", topic=topic)
    patch.authors.add(alice)
    patch.authors.add(bob)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    in_progress_cf.send_closure_notifications()

    assert QueuedMail.objects.count() == 2
    receivers = set(QueuedMail.objects.values_list("receiver", flat=True))
    assert receivers == {alice.email, bob.email}


def test_no_notification_for_author_without_email(bob, in_progress_cf, topic):
    """Authors without email addresses should be skipped."""
    bob.email = ""
    bob.save()

    patch = Patch.objects.create(name="Test Patch", topic=topic)
    patch.authors.add(bob)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    in_progress_cf.send_closure_notifications()

    assert QueuedMail.objects.count() == 0
