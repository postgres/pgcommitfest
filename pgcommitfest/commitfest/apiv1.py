from django.db.models import Prefetch
from django.http import (
    HttpResponse,
)
from django.shortcuts import get_object_or_404

import json
from datetime import date, datetime, timedelta, timezone

from .models import (
    CommitFest,
    MailThread,
    Patch,
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

    raise TypeError(f"Type {type(obj)} not serializable to JSON")


def api_response(payload, status=200, content_type="application/json"):
    response = HttpResponse(
        json.dumps(payload, default=datetime_serializer), status=status
    )
    response["Content-Type"] = content_type
    response["Access-Control-Allow-Origin"] = "*"
    return response


def all_commitfests(request):
    """Return all commitfests, including closed ones."""
    return api_response({"commitfests": list(CommitFest.objects.order_by("id"))})


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
        .select_related("patch")
        .prefetch_related("patch__authors")
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
            entry["threads"] = [t.to_json() for t in poc.patch.mailthread_set.all()]
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

    threads = [t.to_json() for t in patch.mailthread_set.with_has_attachment()]

    return api_response(
        {
            "patch_id": patch.id,
            "name": patch.name,
            "threads": threads,
        }
    )
