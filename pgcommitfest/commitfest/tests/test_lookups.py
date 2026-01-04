import json
from datetime import datetime

import pytest

from pgcommitfest.commitfest.models import Committer, Patch, PatchOnCommitFest, Topic

pytestmark = pytest.mark.django_db


@pytest.fixture
def topic():
    """Create a test topic."""
    return Topic.objects.create(topic="General")


@pytest.fixture
def patches_with_users(users, open_cf, topic):
    """Create patches with authors and reviewers in a commitfest."""
    # Alice is an author on patch 1
    patch1 = Patch.objects.create(name="Test Patch 1", topic=topic)
    patch1.authors.add(users["alice"])
    PatchOnCommitFest.objects.create(
        patch=patch1, commitfest=open_cf, enterdate=datetime.now()
    )

    # Bob is a reviewer on patch 2
    patch2 = Patch.objects.create(name="Test Patch 2", topic=topic)
    patch2.reviewers.add(users["bob"])
    PatchOnCommitFest.objects.create(
        patch=patch2, commitfest=open_cf, enterdate=datetime.now()
    )

    # Dave is a committer on patch 3
    dave_committer = Committer.objects.create(user=users["dave"])
    patch3 = Patch.objects.create(
        name="Test Patch 3", topic=topic, committer=dave_committer
    )
    PatchOnCommitFest.objects.create(
        patch=patch3, commitfest=open_cf, enterdate=datetime.now()
    )

    # Charlie has no involvement in this commitfest
    return {"patch1": patch1, "patch2": patch2, "patch3": patch3}


def test_userlookup_without_cf_requires_login(client, alice):
    """Test that userlookup without cf parameter requires login."""
    response = client.get("/lookups/user/", {"query": "alice"})

    assert response.status_code == 403
    assert b"Login required" in response.content


def test_userlookup_without_cf_works_when_logged_in(client, alice, bob):
    """Test that userlookup without cf parameter works when logged in."""
    client.force_login(bob)
    response = client.get("/lookups/user/", {"query": "alice"})

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "values": [
            {
                "id": alice.id,
                "value": "Alice Anderson (alice)",
            }
        ]
    }


def test_userlookup_with_cf_no_login_required(
    client, alice, open_cf, patches_with_users
):
    """Test that userlookup with cf parameter works without login."""
    response = client.get("/lookups/user/", {"query": "alice", "cf": open_cf.id})

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "values": [
            {
                "id": alice.id,
                "value": "Alice Anderson (alice)",
            }
        ]
    }


def test_userlookup_with_cf_filters_to_commitfest_participants(
    client, alice, bob, dave, open_cf, patches_with_users
):
    """Test that userlookup with cf parameter only returns users in that commitfest."""
    # Search for all users with 'a' in their name
    response = client.get("/lookups/user/", {"query": "a", "cf": open_cf.id})

    assert response.status_code == 200
    # Should return Alice and Dave (both involved) but not Charlie (has 'a' but not involved)
    # Results are returned in order by user ID
    data = json.loads(response.content)
    # Sort by id to ensure consistent ordering
    data["values"].sort(key=lambda x: x["id"])
    expected_values = [
        {
            "id": alice.id,
            "value": "Alice Anderson (alice)",
        },
        {
            "id": dave.id,
            "value": "Dave Davis (dave)",
        },
    ]
    expected_values.sort(key=lambda x: x["id"])
    assert data == {"values": expected_values}


def test_userlookup_with_cf_includes_reviewers(
    client, bob, open_cf, patches_with_users
):
    """Test that userlookup with cf parameter includes reviewers."""
    response = client.get("/lookups/user/", {"query": "bob", "cf": open_cf.id})

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "values": [
            {
                "id": bob.id,
                "value": "Bob Brown (b)",
            }
        ]
    }


def test_userlookup_with_cf_includes_committers(
    client, dave, open_cf, patches_with_users
):
    """Test that userlookup with cf parameter includes committers."""
    response = client.get("/lookups/user/", {"query": "dave", "cf": open_cf.id})

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "values": [
            {
                "id": dave.id,
                "value": "Dave Davis (dave)",
            }
        ]
    }


def test_userlookup_excludes_uninvolved_users(
    client, charlie, open_cf, patches_with_users
):
    """Test that users not involved in the commitfest are excluded."""
    response = client.get("/lookups/user/", {"query": "charlie", "cf": open_cf.id})

    assert response.status_code == 200
    assert json.loads(response.content) == {"values": []}


def test_userlookup_requires_query_parameter(client, commitfests):
    """Test that userlookup returns 404 without query parameter."""
    response = client.get("/lookups/user/")

    assert response.status_code == 404


def test_userlookup_searches_first_name(client, bob, open_cf, patches_with_users):
    """Test that userlookup searches by first name."""
    response = client.get("/lookups/user/", {"query": "Bob", "cf": open_cf.id})

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "values": [
            {
                "id": bob.id,
                "value": "Bob Brown (b)",
            }
        ]
    }


def test_userlookup_searches_last_name(client, bob, open_cf, patches_with_users):
    """Test that userlookup searches by last name."""
    response = client.get("/lookups/user/", {"query": "Brown", "cf": open_cf.id})

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "values": [
            {
                "id": bob.id,
                "value": "Bob Brown (b)",
            }
        ]
    }


def test_userlookup_case_insensitive(client, alice, open_cf, patches_with_users):
    """Test that userlookup is case insensitive."""
    response = client.get("/lookups/user/", {"query": "ALICE", "cf": open_cf.id})

    assert response.status_code == 200
    assert json.loads(response.content) == {
        "values": [
            {
                "id": alice.id,
                "value": "Alice Anderson (alice)",
            }
        ]
    }
