from __future__ import annotations

from django.contrib.syndication.views import Feed

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from icalendar import Calendar, Event

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .models import CommitFest


class ActivityFeed(Feed):
    title = description = "Commitfest Activity Log"
    link = "https://commitfest.postgresql.org/"

    def __init__(self, activity, cf, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.activity = activity
        if cf:
            self.cfid = cf.id
            self.title = self.description = (
                f"PostgreSQL Commitfest {cf.name} Activity Log"
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
    # We use add() instead of the nicer Calendar.new()/Event.new() helpers,
    # because those were only added in icalendar 7.0.0, and production uses
    # the version packaged by Debian trixie, which is 6.0.1.
    name = "PostgreSQL Commitfests"
    description = "Start and end dates of PostgreSQL Commitfests"
    calendar = Calendar()
    calendar.add("version", "2.0")
    calendar.add("prodid", "-//PostgreSQL Commitfest//commitfest.postgresql.org//EN")
    calendar.add("method", "PUBLISH")
    calendar.add("description", description)
    calendar.add("x-wr-caldesc", description)
    calendar.add("name", name)
    calendar.add("x-wr-calname", name)

    now = datetime.now(timezone.utc)
    for cf in commitfests:
        event = Event()
        event.add("uid", f"commitfest-{cf.name}@commitfest.postgresql.org")
        event.add("dtstamp", now)
        event.add("summary", cf.title)
        event.add("dtstart", cf.startdate)
        # DTEND is exclusive for all-day events, so add a day to make the
        # last day of the commitfest show up as included on the calendar.
        event.add("dtend", cf.enddate + timedelta(days=1))
        event.add("description", f"Status: {cf.statusstring}")
        event.add("url", f"https://commitfest.postgresql.org/{cf.id}/")
        calendar.add_component(event)

    return calendar
