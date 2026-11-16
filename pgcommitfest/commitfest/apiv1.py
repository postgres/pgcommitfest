from django.db.models import Prefetch, Q, QuerySet
from django.http import (
    Http404,
    HttpResponse,
)
from django.shortcuts import get_object_or_404

import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

from .models import (
    CommitFest,
    MailThread,
    Patch,
    PatchHistory,
    PatchOnCommitFest,
)


def datetime_serializer(obj):
    # datetime must be checked before date, since datetime is a subclass of date
    if isinstance(obj, datetime):
        return obj.replace(tzinfo=timezone.utc).isoformat()

    if isinstance(obj, date):
        return obj.isoformat()

    if hasattr(obj, "to_json"):
        return obj.to_json()

    if isinstance(obj, QuerySet):
        return list(obj)

    raise TypeError(f"Type {type(obj)} not serializable to JSON")


def api_response(payload, status=200, content_type="application/json"):
    response = HttpResponse(
        json.dumps(payload, default=datetime_serializer), status=status
    )
    response["Content-Type"] = content_type
    response["Access-Control-Allow-Origin"] = "*"
    return response


HISTORY_PAGE_SIZE = 500


def all_commitfests(request):
    """Return all commitfests, including closed ones."""
    return api_response({"commitfests": CommitFest.objects.order_by("id")})


def commitfestst_that_need_ci(request):
    cfs = CommitFest.relevant_commitfests()

    # We continue to run CI on the previous commitfest for a week after it ends
    # to give people some time to move patches over to the next one.
    if cfs["previous"].enddate <= datetime.now(timezone.utc).date() - timedelta(days=7):
        del cfs["previous"]

    del cfs["next_open"]
    del cfs["final"]

    return api_response({"commitfests": cfs})


def commitfest_patches(request, cfid):
    """Return all patches for a commitfest.

    This endpoint provides the data that cfbot previously scraped from the
    commitfest HTML page.

    Threads for every patch can be included with ?include=threads. Unknown
    tokens are ignored.
    """
    cf = get_object_or_404(CommitFest, pk=cfid)

    include = {i.strip() for i in request.GET.get("include", "").split(",")}
    include_threads = "threads" in include

    pocs = (
        PatchOnCommitFest.objects.filter(commitfest=cf)
        .select_related(
            "patch__committer__user", "patch__targetversion", "patch__topic"
        )
        .prefetch_related("patch__authors", "patch__reviewers", "patch__tags")
        .order_by("patch__id")
    )

    if include_threads:
        pocs = pocs.prefetch_related(
            Prefetch(
                "patch__mailthread_set",
                queryset=MailThread.objects.with_has_attachment(),
            )
        )

    patches = []
    for poc in pocs:
        entry = poc.to_json()
        if include_threads:
            entry["threads"] = poc.patch.mailthread_set.all()
        patches.append(entry)

    return api_response(
        {
            "commitfest_id": cf.id,
            "patches": patches,
        }
    )


def patch_threads(request, patch_id):
    """Return thread information for a patch.

    This endpoint provides the data that cfbot previously scraped from the
    patch HTML page to construct thread URLs.
    """
    patch = get_object_or_404(Patch, pk=patch_id)

    threads = patch.mailthread_set.with_has_attachment()

    return api_response(
        {
            "patch_id": patch.id,
            "name": patch.name,
            "threads": threads,
        }
    )


def patch_history(request, patch_id):
    """Return the activity history of a patch, oldest first."""
    # Checking existence avoids loading relations.
    if not Patch.objects.filter(pk=patch_id).exists():
        raise Http404("Patch not found")

    history = (
        PatchHistory.objects.filter(patch_id=patch_id)
        .select_related("by")
        .order_by("date", "id")
    )

    return api_response(
        {
            "patch_id": int(patch_id),
            "history": history,
        }
    )


def history(request):
    """Return the activity history of all patches, oldest first.

    ?since=<iso8601> returns entries from that time on; ?after=<id> breaks
    ties between entries sharing a timestamp. "next" is the URL of the
    following page, or null on the last one. Malformed parameters return
    400 with {"error": "<message>"}.
    """
    since = request.GET.get("since")
    after = request.GET.get("after")

    entries = PatchHistory.objects.select_related("by").order_by("date", "id")

    if since is not None:
        try:
            since = datetime.fromisoformat(since)
        except ValueError:
            return api_response({"error": "since must be an ISO 8601 date"}, 400)
        # Dates are stored as naive UTC
        if since.tzinfo is not None:
            since = since.astimezone(timezone.utc).replace(tzinfo=None)
        entries = entries.filter(date__gte=since)

    if after is not None:
        if since is None:
            return api_response({"error": "after requires since"}, 400)
        try:
            after = int(after)
        except ValueError:
            return api_response({"error": "after must be an integer"}, 400)
        entries = entries.filter(Q(date__gt=since) | Q(id__gt=after))

    page = list(entries[: HISTORY_PAGE_SIZE + 1])
    next_url = None
    if len(page) > HISTORY_PAGE_SIZE:
        page = page[:HISTORY_PAGE_SIZE]
        last = page[-1]
        next_url = "{}?{}".format(
            request.path,
            urlencode({"since": datetime_serializer(last.date), "after": last.id}),
        )

    return api_response({"history": page, "next": next_url})
