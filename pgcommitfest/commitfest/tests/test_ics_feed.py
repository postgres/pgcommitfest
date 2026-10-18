"""
Tests for the /commitfests.ics calendar feed.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from icalendar import Calendar

if TYPE_CHECKING:
    from pgcommitfest.commitfest.models import CommitFest

pytestmark = pytest.mark.django_db


def test_commitfests_ics(client, commitfests: dict[str, CommitFest]):
    """
    Every commitfest, regardless of status, shows up as an all-day VEVENT with
    DTEND being the day after enddate (exclusive).
    """
    response = client.get("/commitfests.ics")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/calendar; charset=utf-8"

    events = Calendar.from_ical(response.content).walk("VEVENT")
    assert len(events) == len(commitfests)
    events_by_uid = {str(event.uid): event for event in events}

    for cf in commitfests.values():
        event = events_by_uid[f"commitfest-{cf.name}@commitfest.postgresql.org"]
        assert event.summary == f"Commitfest {cf.name}"
        assert event.url == f"https://commitfest.postgresql.org/{cf.pk}/"
        assert event.description == f"Status: {cf.statusstring}"
        assert event.start == cf.startdate
        assert event.end == cf.enddate + timedelta(days=1)
