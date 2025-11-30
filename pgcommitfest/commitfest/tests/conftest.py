"""Shared test fixtures for commitfest tests."""

from django.contrib.auth.models import User

from datetime import date

import pytest

from pgcommitfest.commitfest.models import CommitFest


@pytest.fixture
def alice():
    """Create test user Alice."""
    return User.objects.create_user(
        username="alice",
        first_name="Alice",
        last_name="Anderson",
        email="alice@example.com",
    )


@pytest.fixture
def bob():
    """Create test user Bob."""
    return User.objects.create_user(
        username="bob",
        first_name="Bob",
        last_name="Brown",
        email="bob@example.com",
    )


@pytest.fixture
def charlie():
    """Create test user Charlie."""
    return User.objects.create_user(
        username="charlie",
        first_name="Charlie",
        last_name="Chen",
        email="charlie@example.com",
    )


@pytest.fixture
def dave():
    """Create test user Dave."""
    return User.objects.create_user(
        username="dave",
        first_name="Dave",
        last_name="Davis",
        email="dave@example.com",
    )


@pytest.fixture
def users(alice, bob, charlie, dave):
    """Create all test users and return as a dictionary."""
    return {
        "alice": alice,
        "bob": bob,
        "charlie": charlie,
        "dave": dave,
    }


@pytest.fixture
def open_cf():
    """Create an open commitfest."""
    return CommitFest.objects.create(
        name="2025-01",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 1, 1),
        enddate=date(2025, 1, 31),
        draft=False,
    )


@pytest.fixture
def in_progress_cf():
    """Create an in-progress commitfest."""
    return CommitFest.objects.create(
        name="2024-11",
        status=CommitFest.STATUS_INPROGRESS,
        startdate=date(2024, 11, 1),
        enddate=date(2024, 11, 30),
        draft=False,
    )


@pytest.fixture
def recent_closed_cf():
    """Create a recently closed commitfest."""
    return CommitFest.objects.create(
        name="2024-09",
        status=CommitFest.STATUS_CLOSED,
        startdate=date(2024, 9, 1),
        enddate=date(2024, 9, 30),
        draft=False,
    )


@pytest.fixture
def old_closed_cf():
    """Create an old closed commitfest."""
    return CommitFest.objects.create(
        name="2024-07",
        status=CommitFest.STATUS_CLOSED,
        startdate=date(2024, 7, 1),
        enddate=date(2024, 7, 31),
        draft=False,
    )


@pytest.fixture
def draft_cf():
    """Create a draft commitfest."""
    return CommitFest.objects.create(
        name="2025-03-draft",
        status=CommitFest.STATUS_OPEN,
        startdate=date(2025, 3, 1),
        enddate=date(2025, 3, 31),
        draft=True,
    )


@pytest.fixture
def commitfests(open_cf, in_progress_cf, recent_closed_cf, old_closed_cf, draft_cf):
    """Create all test commitfests and return as a dictionary."""
    return {
        "open": open_cf,
        "in_progress": in_progress_cf,
        "recent_previous": recent_closed_cf,
        "old_previous": old_closed_cf,
        "draft": draft_cf,
    }
