from datetime import datetime

import pytest
from freezegun import freeze_time

from pgcommitfest.commitfest.models import (
    CommitFest,
    Patch,
    PatchOnCommitFest,
)

pytestmark = pytest.mark.django_db


@freeze_time("2024-12-05")
def test_inprogress_cf_closes_when_enddate_passed(commitfests, alice):
    """When an in_progress CF's enddate has passed, it should be closed."""
    in_progress_cf = commitfests["in_progress"]
    open_cf = commitfests["open"]

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

    patch.refresh_from_db()
    assert patch.current_commitfest().id == open_cf.id


@freeze_time("2025-01-15")
def test_open_cf_becomes_inprogress_when_startdate_reached(commitfests):
    """When an open CF's startdate is reached, it becomes in_progress."""
    open_cf = commitfests["open"]

    CommitFest._refresh_relevant_commitfests(for_update=False)

    open_cf.refresh_from_db()
    assert open_cf.status == CommitFest.STATUS_INPROGRESS

    new_open = CommitFest.objects.filter(
        status=CommitFest.STATUS_OPEN, draft=False
    ).first()
    assert new_open is not None
    assert new_open.startdate > open_cf.enddate


@freeze_time("2025-02-05")
def test_open_cf_closes_when_enddate_passed(commitfests, alice):
    """When an open CF's enddate has passed (skipping in_progress), it closes."""
    open_cf = commitfests["open"]

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

    new_open = CommitFest.objects.filter(
        status=CommitFest.STATUS_OPEN, draft=False
    ).first()
    assert new_open is not None

    patch.refresh_from_db()
    assert patch.current_commitfest().id == new_open.id


@freeze_time("2025-01-15")
def test_draft_cf_created_when_missing(commitfests):
    """When no draft CF exists, one should be created."""
    # Delete the draft CF
    commitfests["draft"].delete()

    assert not CommitFest.objects.filter(draft=True).exists()

    CommitFest._refresh_relevant_commitfests(for_update=False)

    draft_cf = CommitFest.objects.filter(draft=True).first()
    assert draft_cf is not None
    assert draft_cf.status == CommitFest.STATUS_OPEN


@freeze_time("2025-04-05")
def test_draft_cf_closes_when_enddate_passed(commitfests, alice):
    """When a draft CF's enddate has passed, it should be closed."""
    draft_cf = commitfests["draft"]

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

    new_draft = CommitFest.objects.filter(
        draft=True, status=CommitFest.STATUS_OPEN
    ).first()
    assert new_draft is not None
    assert new_draft.startdate > draft_cf.enddate

    patch.refresh_from_db()
    assert patch.current_commitfest().id == new_draft.id


@freeze_time("2024-11-15")
def test_no_changes_when_up_to_date(commitfests):
    """When commitfests are up to date, no changes should be made."""
    in_progress_cf = commitfests["in_progress"]
    open_cf = commitfests["open"]
    draft_cf = commitfests["draft"]

    initial_cf_count = CommitFest.objects.count()

    CommitFest._refresh_relevant_commitfests(for_update=False)

    in_progress_cf.refresh_from_db()
    open_cf.refresh_from_db()
    draft_cf.refresh_from_db()

    assert in_progress_cf.status == CommitFest.STATUS_INPROGRESS
    assert open_cf.status == CommitFest.STATUS_OPEN
    assert draft_cf.status == CommitFest.STATUS_OPEN
    assert CommitFest.objects.count() == initial_cf_count
