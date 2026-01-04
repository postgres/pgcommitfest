from django.conf import settings

import base64
from datetime import date, datetime, timedelta
from email import message_from_string

import pytest

from pgcommitfest.commitfest.models import (
    CfbotBranch,
    CommitFest,
    Patch,
    PatchHistory,
    PatchOnCommitFest,
    PendingNotification,
    Topic,
)
from pgcommitfest.mailqueue.models import QueuedMail
from pgcommitfest.userprofile.models import UserProfile

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


def test_no_notification_for_withdrawn_patches(alice, in_progress_cf, open_cf, topic):
    """Withdrawn patches should not receive notifications or be auto-moved."""
    patch = Patch.objects.create(
        name="Withdrawn Patch",
        topic=topic,
        lastmail=datetime.now() - timedelta(days=5),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        leavedate=datetime.now(),
        status=PatchOnCommitFest.STATUS_WITHDRAWN,
    )

    moved_patch_ids = in_progress_cf.auto_move_active_patches()
    in_progress_cf.send_closure_notifications(moved_patch_ids)

    assert patch.id not in moved_patch_ids
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
    """Each author of open patches should receive their own notification (if opted in)."""
    # Bob also needs notify_all_author enabled to receive closure emails
    UserProfile.objects.create(user=bob, notify_all_author=True)

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


def test_notification_includes_next_commitfest_info(
    alice, in_progress_cf, open_cf, topic
):
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


def test_coauthors_both_receive_notification(alice, bob, in_progress_cf, topic):
    """Both co-authors of a patch should receive notifications (if opted in)."""
    # Bob also needs notify_all_author enabled to receive closure emails
    UserProfile.objects.create(user=bob, notify_all_author=True)

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
    """Authors without email addresses should be skipped even if opted in."""
    UserProfile.objects.create(user=bob, notify_all_author=True)
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


def test_no_notification_for_author_without_notify_all_author(
    bob, in_progress_cf, topic
):
    """Authors without notify_all_author enabled should not receive closure notifications."""
    # bob has no UserProfile, so notify_all_author is not enabled
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


# Auto-move tests


def test_auto_move_patch_with_recent_email_activity(
    alice, bob, in_progress_cf, open_cf, topic
):
    """Patches with recent email activity should be auto-moved to the next commitfest."""
    patch = Patch.objects.create(
        name="Active Patch",
        topic=topic,
        lastmail=datetime.now() - timedelta(days=5),
    )
    patch.authors.add(alice)
    patch.subscribers.add(bob)  # Bob subscribes to get notifications
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    moved_patch_ids = in_progress_cf.auto_move_active_patches()
    in_progress_cf.send_closure_notifications(moved_patch_ids)

    # Patch should be moved
    patch.refresh_from_db()
    assert patch.current_commitfest().id == open_cf.id

    # Move should create a history entry with by_cfbot=True
    history = PatchHistory.objects.filter(patch=patch).first()
    assert history is not None
    assert history.by_cfbot is True
    assert "Moved from CF" in history.what

    # PendingNotification should be created for author and subscriber
    assert PendingNotification.objects.filter(history=history, user=alice).exists()
    assert PendingNotification.objects.filter(history=history, user=bob).exists()

    # No closure email for moved patches (move triggers its own notification)
    assert QueuedMail.objects.count() == 0


def test_no_auto_move_without_email_activity(alice, in_progress_cf, open_cf, topic):
    """Patches without recent email activity should NOT be auto-moved."""
    patch = Patch.objects.create(
        name="Inactive Patch",
        topic=topic,
        lastmail=datetime.now()
        - timedelta(days=settings.AUTO_MOVE_EMAIL_ACTIVITY_DAYS + 10),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    moved_patch_ids = in_progress_cf.auto_move_active_patches()
    in_progress_cf.send_closure_notifications(moved_patch_ids)

    # Patch should NOT be moved
    patch.refresh_from_db()
    assert patch.current_commitfest().id == in_progress_cf.id

    # Closure email should be sent for non-moved patches
    assert QueuedMail.objects.count() == 1
    mail = QueuedMail.objects.first()
    body = get_email_body(mail)
    assert "Inactive Patch" in body
    assert "need" in body  # "needs attention"


def test_no_auto_move_when_failing_too_long(alice, in_progress_cf, open_cf, topic):
    """Patches failing CI for too long should NOT be auto-moved even with recent activity."""
    patch = Patch.objects.create(
        name="Failing Patch",
        topic=topic,
        lastmail=datetime.now() - timedelta(days=5),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    # Add CfbotBranch with long-standing failure
    CfbotBranch.objects.create(
        patch=patch,
        branch_id=1,
        branch_name="test-branch",
        apply_url="https://example.com",
        status="failed",
        failing_since=datetime.now()
        - timedelta(days=settings.AUTO_MOVE_MAX_FAILING_DAYS + 10),
    )

    moved_patch_ids = in_progress_cf.auto_move_active_patches()
    in_progress_cf.send_closure_notifications(moved_patch_ids)

    # Patch should NOT be moved
    patch.refresh_from_db()
    assert patch.current_commitfest().id == in_progress_cf.id


def test_auto_move_when_failing_within_threshold(alice, in_progress_cf, open_cf, topic):
    """Patches failing CI within the threshold should still be auto-moved."""
    patch = Patch.objects.create(
        name="Recently Failing Patch",
        topic=topic,
        lastmail=datetime.now() - timedelta(days=5),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    # Add CfbotBranch with recent failure (within threshold)
    CfbotBranch.objects.create(
        patch=patch,
        branch_id=2,
        branch_name="test-branch-2",
        apply_url="https://example.com",
        status="failed",
        failing_since=datetime.now()
        - timedelta(days=settings.AUTO_MOVE_MAX_FAILING_DAYS - 5),
    )

    moved_patch_ids = in_progress_cf.auto_move_active_patches()
    in_progress_cf.send_closure_notifications(moved_patch_ids)

    # Patch should be moved (failure is recent enough)
    patch.refresh_from_db()
    assert patch.current_commitfest().id == open_cf.id

    # No closure email for moved patches
    assert QueuedMail.objects.count() == 0


def test_no_auto_move_without_next_commitfest(alice, in_progress_cf, topic):
    """Patches should not be auto-moved if there's no next commitfest."""
    patch = Patch.objects.create(
        name="Active Patch No Next CF",
        topic=topic,
        lastmail=datetime.now() - timedelta(days=5),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    moved_patch_ids = in_progress_cf.auto_move_active_patches()
    in_progress_cf.send_closure_notifications(moved_patch_ids)

    # Patch should NOT be moved (no next CF)
    patch.refresh_from_db()
    assert patch.current_commitfest().id == in_progress_cf.id


def test_no_auto_move_with_null_lastmail(alice, in_progress_cf, open_cf, topic):
    """Patches with no email activity (null lastmail) should NOT be auto-moved."""
    patch = Patch.objects.create(
        name="No Activity Patch",
        topic=topic,
        lastmail=None,
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    moved_patch_ids = in_progress_cf.auto_move_active_patches()

    assert patch.id not in moved_patch_ids
    patch.refresh_from_db()
    assert patch.current_commitfest().id == in_progress_cf.id


def test_auto_move_patch_without_cfbot_branch(alice, in_progress_cf, open_cf, topic):
    """Patches with recent activity but no CI branch should be auto-moved."""
    patch = Patch.objects.create(
        name="No CI Patch",
        topic=topic,
        lastmail=datetime.now() - timedelta(days=5),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    # No CfbotBranch created - CI never ran

    moved_patch_ids = in_progress_cf.auto_move_active_patches()
    in_progress_cf.send_closure_notifications(moved_patch_ids)

    assert patch.id in moved_patch_ids
    patch.refresh_from_db()
    assert patch.current_commitfest().id == open_cf.id

    # No closure email for moved patches
    assert QueuedMail.objects.count() == 0


def test_regular_cf_does_not_move_to_draft_cf(alice, in_progress_cf, topic):
    """Regular commitfest should not move patches to a draft commitfest."""
    # Create only a draft CF as the "next" option (should be ignored)
    CommitFest.objects.create(
        name="2025-05-draft",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 5, 1),
        enddate=date(2025, 5, 31),
        draft=True,
    )

    patch = Patch.objects.create(
        name="Regular Patch",
        topic=topic,
        lastmail=datetime.now() - timedelta(days=5),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    moved_patch_ids = in_progress_cf.auto_move_active_patches()

    # Should not be moved since only draft CF is available
    assert patch.id not in moved_patch_ids
    patch.refresh_from_db()
    assert patch.current_commitfest().id == in_progress_cf.id


def test_draft_cf_moves_active_patches_to_next_draft(alice, bob, topic):
    """Active patches in a draft commitfest should be auto-moved to the next draft CF."""
    # Create two draft CFs - one closing and one to receive patches
    closing_draft_cf = CommitFest.objects.create(
        name="2025-03-draft",
        status=CommitFest.STATUS_INPROGRESS,
        startdate=date(2025, 3, 1),
        enddate=date(2025, 3, 31),
        draft=True,
    )
    next_draft_cf = CommitFest.objects.create(
        name="2026-03-draft",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2026, 3, 1),
        enddate=date(2026, 3, 31),
        draft=True,
    )

    patch = Patch.objects.create(
        name="Draft Patch",
        topic=topic,
        lastmail=datetime.now() - timedelta(days=5),
    )
    patch.authors.add(alice)
    patch.subscribers.add(bob)  # Bob subscribes to get notifications
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=closing_draft_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    moved_patch_ids = closing_draft_cf.auto_move_active_patches()
    closing_draft_cf.send_closure_notifications(moved_patch_ids)

    # Patch should be moved to the next draft CF
    patch.refresh_from_db()
    assert patch.current_commitfest().id == next_draft_cf.id

    # Move should create a history entry with by_cfbot=True
    history = PatchHistory.objects.filter(patch=patch).first()
    assert history is not None
    assert history.by_cfbot is True

    # PendingNotification should be created for author and subscriber
    assert PendingNotification.objects.filter(history=history, user=alice).exists()
    assert PendingNotification.objects.filter(history=history, user=bob).exists()

    # No closure email for moved patches
    assert QueuedMail.objects.count() == 0
