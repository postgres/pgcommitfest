from django.test import override_settings

import json
from datetime import date

import pytest

from pgcommitfest.commitfest.models import CommitFest

pytestmark = pytest.mark.django_db


@pytest.fixture
def commitfests():
    """Create test commitfests with various statuses."""
    return {
        "open": CommitFest.objects.create(
            name="2025-01",
            status=CommitFest.STATUS_OPEN,
            startdate=date(2025, 1, 1),
            enddate=date(2025, 1, 31),
            draft=False,
        ),
        "in_progress": CommitFest.objects.create(
            name="2024-11",
            status=CommitFest.STATUS_INPROGRESS,
            startdate=date(2024, 11, 1),
            enddate=date(2024, 11, 30),
            draft=False,
        ),
        "recent_previous": CommitFest.objects.create(
            name="2024-09",
            status=CommitFest.STATUS_CLOSED,
            startdate=date(2024, 9, 1),
            enddate=date(2024, 9, 30),
            draft=False,
        ),
        "old_previous": CommitFest.objects.create(
            name="2024-07",
            status=CommitFest.STATUS_CLOSED,
            startdate=date(2024, 7, 1),
            enddate=date(2024, 7, 31),
            draft=False,
        ),
        "draft": CommitFest.objects.create(
            name="2025-03-draft",
            status=CommitFest.STATUS_OPEN,
            startdate=date(2025, 3, 1),
            enddate=date(2025, 3, 31),
            draft=True,
        ),
    }


def test_needs_ci_endpoint(client, commitfests):
    """Test the /api/v1/commitfests/needs_ci endpoint returns correct data."""
    with override_settings(AUTO_CREATE_COMMITFESTS=False):
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
