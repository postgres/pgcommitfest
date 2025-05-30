from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import avoid_wrapping
from django.utils.timesince import MONTHS_DAYS
from django.utils.timezone import is_aware
from django.utils.translation import ngettext_lazy

import datetime
import string
from uuid import uuid4

from pgcommitfest.commitfest.models import CommitFest, PatchOnCommitFest

register = template.Library()


@register.filter(name="commitfeststatusstring")
@stringfilter
def commitfeststatusstring(value):
    i = int(value)
    return [v for k, v in CommitFest._STATUS_CHOICES if k == i][0]


@register.filter(name="commitfeststatuslabel")
@stringfilter
def commitfeststatuslabel(value):
    i = int(value)
    return [v for k, v in CommitFest._STATUS_LABELS if k == i][0]


@register.filter(name="patchstatusstring")
@stringfilter
def patchstatusstring(value):
    i = int(value)
    return [v for k, v in PatchOnCommitFest._STATUS_CHOICES if k == i][0]


@register.filter(name="patchstatuslabel")
@stringfilter
def patchstatuslabel(value):
    i = int(value)
    return [v for k, v in PatchOnCommitFest._STATUS_LABELS if k == i][0]


@register.filter(name="tagname")
def tagname(value, arg):
    """
    Looks up a tag by ID and returns its name. The filter value is the map of
    tags, and the argument is the ID. (Unlike tagcolor, there is no
    argument-less variant; just use tag.name directly.)

    Example:
      tag_map|tagname:tag_id
    """
    return value[arg].name


@register.filter(name="tagcolor")
def tagcolor(value, key=None):
    """
    Returns the color code of a tag. The filter value is either a single tag, in
    which case no argument should be given, or a map of tags with the tag ID as
    the argument, as with the tagname filter.

    Since color codes are injected into CSS, any nonconforming inputs are
    replaced with black here. (Prefer `tag|tagcolor` over `tag.color` in
    templates, for this reason.)
    """
    if key is not None:
        code = value[key].color
    else:
        code = value.color

    if (
        len(code) == 7
        and code.startswith("#")
        and all(c in string.hexdigits for c in code[1:])
    ):
        return code

    return "#000000"


@register.filter(is_safe=True)
def label_class(value, arg):
    return value.label_tag(attrs={"class": arg})


@register.filter(is_safe=True)
def field_class(value, arg):
    return value.as_widget(attrs={"class": arg})


@register.filter(name="alertmap")
@stringfilter
def alertmap(value):
    if value == "error":
        return "alert-danger"
    elif value == "warning":
        return "alert-warning"
    elif value == "success":
        return "alert-success"
    else:
        return "alert-info"


# Generate a GET parameter that's unique per startup of the python process to
# bust the cache of the client, so that it pulls in possibly updated JS/CSS
# files.
STATIC_FILE_PARAM = f"v={uuid4()}"


# This GET parameter should be added to every one of our static files.
@register.simple_tag
def static_file_param():
    return STATIC_FILE_PARAM


@register.filter(name="hidemail")
@stringfilter
def hidemail(value):
    return value.replace("@", " at ")


TIME_STRINGS = {
    "year": ngettext_lazy("%(num)d year", "%(num)d years", "num"),
    "month": ngettext_lazy("%(num)d month", "%(num)d months", "num"),
    "week": ngettext_lazy("%(num)d week", "%(num)d weeks", "num"),
    "day": ngettext_lazy("%(num)d day", "%(num)d days", "num"),
    "hour": ngettext_lazy("%(num)d hour", "%(num)d hours", "num"),
    "minute": ngettext_lazy("%(num)d minute", "%(num)d minutes", "num"),
    "second": ngettext_lazy("%(num)d second", "%(num)d seconds", "num"),
}

TIME_STRINGS_KEYS = list(TIME_STRINGS.keys())

TIME_CHUNKS = [
    60 * 60 * 24 * 7,  # week
    60 * 60 * 24,  # day
    60 * 60,  # hour
    60,  # minute
    1,  # second
]


@register.simple_tag(takes_context=True)
def cfsince(context, d):
    if (
        context["user"].is_authenticated
        and not context["userprofile"].show_relative_timestamps
    ):
        return f"since {d}"
    partials = cf_duration_partials(d)
    if partials is None:
        return "since some time in the future"

    # Find the first non-zero part (if any) and then build the result, until
    # depth.
    i = 0
    for i, value in enumerate(partials):
        if value != 0:
            break
    else:
        return "since now"

    value = partials[i]
    name = TIME_STRINGS_KEYS[i]
    if name == "day" and value == 1:
        return avoid_wrapping("since yesterday")
    return avoid_wrapping("since " + TIME_STRINGS[name] % {"num": value})


@register.simple_tag()
def cfwhen(d):
    partials = cf_duration_partials(d)
    if partials is None:
        return "some time in the future"

    # Find the first non-zero part (if any) and then build the result, until
    # depth.
    i = 0
    for i, value in enumerate(partials):
        if value != 0:
            break
    else:
        return "now"

    value = partials[i]
    name = TIME_STRINGS_KEYS[i]

    if name == "day" and value == 1:
        return avoid_wrapping("yesterday")

    return avoid_wrapping(TIME_STRINGS[name] % {"num": value} + " ago")


def cf_duration_partials(d):
    """
    Take two datetime objects and return the time between d and now as a nicely
    formatted string, e.g. "10 minutes". If d occurs after now, return
    "0 minutes".

    Units used are years, months, weeks, days, hours, and minutes.
    Seconds and microseconds are ignored.

    The algorithm takes into account the varying duration of years and months.
    There is exactly "1 year, 1 month" between 2013/02/10 and 2014/03/10,
    but also between 2007/08/10 and 2008/09/10 despite the delta being 393 days
    in the former case and 397 in the latter.

    Adapted from Django's timesince function.
    """
    # Convert datetime.date to datetime.datetime for comparison.
    if not isinstance(d, datetime.datetime):
        d = datetime.datetime(d.year, d.month, d.day)

    now = datetime.datetime.now(d.tzinfo if is_aware(d) else None)

    delta = now - d

    # Ignore microseconds.
    since = delta.days * 24 * 60 * 60 + delta.seconds
    if since < 0:
        # d is in the future compared to now, stop processing.
        return None

    # Get years and months.
    total_months = (now.year - d.year) * 12 + (now.month - d.month)
    if d.day > now.day or (d.day == now.day and d.time() > now.time()):
        total_months -= 1
    years, months = divmod(total_months, 12)

    # Calculate the remaining time.
    # Create a "pivot" datetime shifted from d by years and months, then use
    # that to determine the other parts.
    if years or months:
        pivot_year = d.year + years
        pivot_month = d.month + months
        if pivot_month > 12:
            pivot_month -= 12
            pivot_year += 1
        pivot = datetime.datetime(
            pivot_year,
            pivot_month,
            min(MONTHS_DAYS[pivot_month - 1], d.day),
            d.hour,
            d.minute,
            d.second,
            tzinfo=d.tzinfo,
        )
    else:
        pivot = d
    remaining_time = (now - pivot).total_seconds()
    partials = [years, months]
    for chunk in TIME_CHUNKS:
        count = int(remaining_time // chunk)
        partials.append(count)
        remaining_time -= chunk * count

    return partials
