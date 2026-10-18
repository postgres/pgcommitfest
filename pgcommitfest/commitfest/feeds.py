from __future__ import annotations

from django.contrib.syndication.views import Feed

from datetime import timedelta
from typing import TYPE_CHECKING

from icalendar import Calendar, Event

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .models import CommitFest


class ActivityFeed(Feed):
    title = description = "Commitfest Activity Log"
    link = "https://commitfest.postgresql.org/"

    def __init__(self, activity, cf, *args, **kwargs):
        super(ActivityFeed, self).__init__(*args, **kwargs)
        self.activity = activity
        if cf:
            self.cfid = cf.id
            self.title = self.description = (
                "PostgreSQL Commitfest {0} Activity Log".format(cf.name)
            )
        else:
            self.cfid = None

    def items(self):
        return self.activity

    def item_title(self, item):
        return item["name"]

    def item_description(self, item):
        return (
            "<div>Patch: {name}</div><div>User: {by}</div>\n<div>{what}</div>".format(
                **item
            )
        )

    def item_link(self, item):
        return "https://commitfest.postgresql.org/patch/{patchid}/".format(**item)

    def item_pubdate(self, item):
        return item["date"]


def calendar(commitfests: Iterable[CommitFest]) -> Calendar:
    """
    Build an RFC 5545 iCalendar document with one all-day VEVENT per
    commitfest, covering its start and end date.
    """
    calendar = Calendar.new(
        prodid="-//PostgreSQL Commitfest//commitfest.postgresql.org//EN",
        name="PostgreSQL Commitfests",
        description="Start and end dates of PostgreSQL Commitfests",
        method="PUBLISH",
    )

    for cf in commitfests:
        event = Event.new(
            uid=f"commitfest-{cf.name}@commitfest.postgresql.org",
            summary=cf.title,
            start=cf.startdate,
            # DTEND is exclusive for all-day events, so add a day to make the
            # last day of the commitfest show up as included on the calendar.
            end=cf.enddate + timedelta(days=1),
            description=f"Status: {cf.statusstring}",
            url=f"https://commitfest.postgresql.org/{cf.id}/",
        )
        calendar.add_component(event)

    return calendar
