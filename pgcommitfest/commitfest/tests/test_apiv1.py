import json
from datetime import datetime, timezone

import pytest

from pgcommitfest.commitfest.models import (
    MailThread,
    Patch,
    PatchOnCommitFest,
)

pytestmark = pytest.mark.django_db


def test_needs_ci_endpoint(client, commitfests):
    """Test the /api/v1/commitfests/needs_ci endpoint returns correct data."""
    response = client.get("/api/v1/commitfests/needs_ci")

    # Check response metadata
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert response["Access-Control-Allow-Origin"] == "*"

    # Parse and compare response
    data = json.loads(response.content)

    expected = {
        "commitfests": {
            "open": {
                "id": commitfests["open"].id,
                "name": "2025-01",
                "status": "Open",
                "startdate": "2025-01-01",
                "enddate": "2025-01-31",
            },
            "in_progress": {
                "id": commitfests["in_progress"].id,
                "name": "2024-11",
                "status": "In Progress",
                "startdate": "2024-11-01",
                "enddate": "2024-11-30",
            },
            "draft": {
                "id": commitfests["draft"].id,
                "name": "2025-03-draft",
                "status": "Open",
                "startdate": "2025-03-01",
                "enddate": "2025-03-31",
            },
        }
    }

    assert data == expected


def test_commitfest_patches_endpoint(client, open_cf, alice, bob):
    """Test the /api/v1/commitfests/<id>/patches endpoint."""
    # Create test patches
    patch1 = Patch.objects.create(name="Add feature X")
    patch1.authors.add(alice)
    patch1.lastmail = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    patch1.save()

    patch2 = Patch.objects.create(name="Fix bug Y")
    patch2.authors.add(alice, bob)
    patch2.save()

    # Link patches to commitfest
    PatchOnCommitFest.objects.create(
        patch=patch1,
        commitfest=open_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )
    PatchOnCommitFest.objects.create(
        patch=patch2,
        commitfest=open_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_AUTHOR,
    )

    response = client.get(f"/api/v1/commitfests/{open_cf.id}/patches")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert response["Access-Control-Allow-Origin"] == "*"

    data = json.loads(response.content)

    assert data["commitfest_id"] == open_cf.id
    assert len(data["patches"]) == 2

    # Patches are ordered by id
    p1 = data["patches"][0]
    assert p1["id"] == patch1.id
    assert p1["name"] == "Add feature X"
    assert p1["status"] == "Needs review"
    assert p1["authors"] == ["Alice Anderson"]
    assert p1["last_email_time"] == "2025-01-15T10:30:00+00:00"

    p2 = data["patches"][1]
    assert p2["id"] == patch2.id
    assert p2["name"] == "Fix bug Y"
    assert p2["status"] == "Waiting on Author"
    assert sorted(p2["authors"]) == ["Alice Anderson", "Bob Brown"]
    assert p2["last_email_time"] is None


def test_commitfest_patches_endpoint_not_found(client, commitfests):
    """Test the patches endpoint returns 404 for non-existent commitfest."""
    response = client.get("/api/v1/commitfests/99999/patches")
    assert response.status_code == 404


def test_patch_threads_endpoint(client, open_cf, alice):
    """Test the /api/v1/patches/<id>/threads endpoint."""
    patch = Patch.objects.create(name="Test patch")
    patch.authors.add(alice)

    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=open_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    # Create mail threads
    thread1 = MailThread.objects.create(
        messageid="abc123@example.com",
        subject="[PATCH] Test patch v1",
        firstmessage=datetime(2025, 1, 10, 9, 0, 0, tzinfo=timezone.utc),
        firstauthor="alice@example.com",
        latestmessage=datetime(2025, 1, 12, 14, 30, 0, tzinfo=timezone.utc),
        latestauthor="bob@example.com",
        latestsubject="Re: [PATCH] Test patch v1",
        latestmsgid="def456@example.com",
    )
    patch.mailthread_set.add(thread1)

    response = client.get(f"/api/v1/patches/{patch.id}/threads")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"

    data = json.loads(response.content)

    assert data["patch_id"] == patch.id
    assert data["name"] == "Test patch"
    assert len(data["threads"]) == 1

    t = data["threads"][0]
    assert t["messageid"] == "abc123@example.com"
    assert t["subject"] == "[PATCH] Test patch v1"
    assert t["latest_message_id"] == "def456@example.com"
    assert t["latest_message_time"] == "2025-01-12T14:30:00+00:00"
    assert t["has_attachment"] is False


def test_patch_threads_endpoint_not_found(client, commitfests):
    """Test the threads endpoint returns 404 for non-existent patch."""
    response = client.get("/api/v1/patches/99999/threads")
    assert response.status_code == 404
