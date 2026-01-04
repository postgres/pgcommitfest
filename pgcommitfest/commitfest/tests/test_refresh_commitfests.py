from datetime import date, datetime

import pytest
from freezegun import freeze_time

from pgcommitfest.commitfest.models import (
    CommitFest,
    Patch,
    PatchOnCommitFest,
)
from pgcommitfest.userprofile.models import UserProfile


@pytest.fixture
def alice(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
    )
    UserProfile.objects.create(user=user, notify_all_author=True)
    return user


def create_closed_cf(name, startdate, enddate):
    """Helper to create a closed CF for padding."""
    return CommitFest.objects.create(
        name=name,
        status=CommitFest.STATUS_CLOSED,
        startdate=startdate,
        enddate=enddate,
    )


@pytest.mark.django_db
@freeze_time("2024-12-05")
def test_inprogress_cf_closes_when_enddate_passed(alice):
    """When an in_progress CF's enddate has passed, it should be closed."""
    # Create some closed CFs for padding (relevant_commitfests needs history)
    create_closed_cf("2024-07", date(2024, 7, 1), date(2024, 7, 31))
    create_closed_cf("2024-09", date(2024, 9, 1), date(2024, 9, 30))

    # Create an in_progress CF that ended
    in_progress_cf = CommitFest.objects.create(
        name="2024-11",
        status=CommitFest.STATUS_INPROGRESS,
        startdate=date(2024, 11, 1),
        enddate=date(2024, 11, 30),
    )
    # Create the next open CF (required for auto_move)
    open_cf = CommitFest.objects.create(
        name="2025-01",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 1, 1),
        enddate=date(2025, 1, 31),
    )
    # Create draft CF
    CommitFest.objects.create(
        name="2025-draft",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2024, 7, 1),
        enddate=date(2025, 3, 31),
        draft=True,
    )

    # Create a patch with recent activity that should be auto-moved
    patch = Patch.objects.create(
        name="Test Patch",
        lastmail=datetime(2024, 11, 25),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=in_progress_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    CommitFest._refresh_relevant_commitfests(for_update=False)

    in_progress_cf.refresh_from_db()
    assert in_progress_cf.status == CommitFest.STATUS_CLOSED

    # Patch should have been moved to the open CF
    patch.refresh_from_db()
    assert patch.current_commitfest().id == open_cf.id


@pytest.mark.django_db
@freeze_time("2025-01-15")
def test_open_cf_becomes_inprogress_when_startdate_reached():
    """When an open CF's startdate is reached, it becomes in_progress."""
    # Create some closed CFs for padding
    create_closed_cf("2024-07", date(2024, 7, 1), date(2024, 7, 31))
    create_closed_cf("2024-09", date(2024, 9, 1), date(2024, 9, 30))
    create_closed_cf("2024-11", date(2024, 11, 1), date(2024, 11, 30))

    open_cf = CommitFest.objects.create(
        name="2025-01",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 1, 1),
        enddate=date(2025, 1, 31),
    )
    # Create draft CF
    CommitFest.objects.create(
        name="2025-draft",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2024, 7, 1),
        enddate=date(2025, 3, 31),
        draft=True,
    )

    CommitFest._refresh_relevant_commitfests(for_update=False)

    open_cf.refresh_from_db()
    assert open_cf.status == CommitFest.STATUS_INPROGRESS

    # A new open CF should have been created
    new_open = CommitFest.objects.filter(
        status=CommitFest.STATUS_OPEN, draft=False
    ).first()
    assert new_open is not None
    assert new_open.startdate > open_cf.enddate


@pytest.mark.django_db
@freeze_time("2025-02-05")
def test_open_cf_closes_when_enddate_passed(alice):
    """When an open CF's enddate has passed (skipping in_progress), it closes."""
    # Create some closed CFs for padding
    create_closed_cf("2024-07", date(2024, 7, 1), date(2024, 7, 31))
    create_closed_cf("2024-09", date(2024, 9, 1), date(2024, 9, 30))
    create_closed_cf("2024-11", date(2024, 11, 1), date(2024, 11, 30))

    open_cf = CommitFest.objects.create(
        name="2025-01",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 1, 1),
        enddate=date(2025, 1, 31),
    )
    # Create draft CF
    CommitFest.objects.create(
        name="2025-draft",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2024, 7, 1),
        enddate=date(2025, 3, 31),
        draft=True,
    )

    # Create a patch with recent activity
    patch = Patch.objects.create(
        name="Test Patch",
        lastmail=datetime(2025, 1, 25),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=open_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    CommitFest._refresh_relevant_commitfests(for_update=False)

    open_cf.refresh_from_db()
    assert open_cf.status == CommitFest.STATUS_CLOSED

    # A new open CF should have been created
    new_open = CommitFest.objects.filter(
        status=CommitFest.STATUS_OPEN, draft=False
    ).first()
    assert new_open is not None

    # Patch should have been moved to the new open CF
    patch.refresh_from_db()
    assert patch.current_commitfest().id == new_open.id


@pytest.mark.django_db
@freeze_time("2025-01-15")
def test_draft_cf_created_when_missing():
    """When no draft CF exists, one should be created."""
    # Create closed CFs for padding
    create_closed_cf("2024-07", date(2024, 7, 1), date(2024, 7, 31))
    create_closed_cf("2024-09", date(2024, 9, 1), date(2024, 9, 30))
    create_closed_cf("2024-11", date(2024, 11, 1), date(2024, 11, 30))

    # Create only regular CFs
    CommitFest.objects.create(
        name="2025-01",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 3, 1),
        enddate=date(2025, 3, 31),
    )

    assert not CommitFest.objects.filter(draft=True).exists()

    CommitFest._refresh_relevant_commitfests(for_update=False)

    # A draft CF should have been created
    draft_cf = CommitFest.objects.filter(draft=True).first()
    assert draft_cf is not None
    assert draft_cf.status == CommitFest.STATUS_OPEN


@pytest.mark.django_db
@freeze_time("2025-04-05")
def test_draft_cf_closes_when_enddate_passed(alice):
    """When a draft CF's enddate has passed, it should be closed."""
    # Create closed CFs for padding
    create_closed_cf("2024-07", date(2024, 7, 1), date(2024, 7, 31))
    create_closed_cf("2024-09", date(2024, 9, 1), date(2024, 9, 30))
    create_closed_cf("2024-11", date(2024, 11, 1), date(2024, 11, 30))

    # Create an open regular CF (required)
    CommitFest.objects.create(
        name="2025-03",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 5, 1),
        enddate=date(2025, 5, 31),
    )

    # Create a draft CF that ended
    draft_cf = CommitFest.objects.create(
        name="2025-draft",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 1, 1),
        enddate=date(2025, 3, 31),
        draft=True,
    )

    # Create a patch with recent activity
    patch = Patch.objects.create(
        name="Draft Patch",
        lastmail=datetime(2025, 3, 25),
    )
    patch.authors.add(alice)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=draft_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    CommitFest._refresh_relevant_commitfests(for_update=False)

    draft_cf.refresh_from_db()
    assert draft_cf.status == CommitFest.STATUS_CLOSED

    # A new draft CF should have been created
    new_draft = CommitFest.objects.filter(
        draft=True, status=CommitFest.STATUS_OPEN
    ).first()
    assert new_draft is not None
    assert new_draft.startdate > draft_cf.enddate

    # Patch should have been moved to the new draft CF
    patch.refresh_from_db()
    assert patch.current_commitfest().id == new_draft.id


@pytest.mark.django_db
@freeze_time("2025-01-15")
def test_no_changes_when_up_to_date():
    """When commitfests are up to date, no changes should be made."""
    # Create closed CFs for padding
    create_closed_cf("2024-07", date(2024, 7, 1), date(2024, 7, 31))
    create_closed_cf("2024-09", date(2024, 9, 1), date(2024, 9, 30))

    # Create CFs that are all up to date
    in_progress_cf = CommitFest.objects.create(
        name="2025-01",
        status=CommitFest.STATUS_INPROGRESS,
        startdate=date(2025, 1, 1),
        enddate=date(2025, 1, 31),
    )
    open_cf = CommitFest.objects.create(
        name="2025-03",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 3, 1),
        enddate=date(2025, 3, 31),
    )
    draft_cf = CommitFest.objects.create(
        name="2025-draft",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 1, 1),
        enddate=date(2025, 3, 31),
        draft=True,
    )

    initial_cf_count = CommitFest.objects.count()

    CommitFest._refresh_relevant_commitfests(for_update=False)

    # All statuses should remain unchanged
    in_progress_cf.refresh_from_db()
    open_cf.refresh_from_db()
    draft_cf.refresh_from_db()

    assert in_progress_cf.status == CommitFest.STATUS_INPROGRESS
    assert open_cf.status == CommitFest.STATUS_OPEN
    assert draft_cf.status == CommitFest.STATUS_OPEN

    # No new CFs should have been created
    assert CommitFest.objects.count() == initial_cf_count
