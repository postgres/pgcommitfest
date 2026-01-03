from django.contrib.auth.models import User
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseForbidden

import json

from .models import Patch


def userlookup(request):
    query = request.GET.get("query", None)
    cf = request.GET.get("cf", None)

    if not query:
        raise Http404()

    # Start with base filters for active users matching the query
    users = User.objects.filter(
        Q(is_active=True),
        Q(username__icontains=query)
        | Q(first_name__icontains=query)
        | Q(last_name__icontains=query),
    )

    # If no commitfest filter is provided, require login
    if not cf:
        if not request.user.is_authenticated:
            return HttpResponseForbidden(
                "Login required when not filtering by commitfest"
            )
    else:
        # Filter users to only those who have participated in the specified commitfest.
        # We collect user IDs via a single query to avoid a complex join.
        patches = Patch.objects.filter(patchoncommitfest__commitfest_id=cf)
        user_ids = set()
        for author_id, reviewer_id, committer_user_id in patches.values_list(
            "authors", "reviewers", "committer__user_id"
        ):
            if author_id:
                user_ids.add(author_id)
            if reviewer_id:
                user_ids.add(reviewer_id)
            if committer_user_id:
                user_ids.add(committer_user_id)
        users = users.filter(id__in=user_ids)

    return HttpResponse(
        json.dumps(
            {
                "values": [
                    {
                        "id": u.id,
                        "value": f"{u.get_full_name()} ({u.username})",
                    }
                    for u in users
                ],
            }
        ),
        content_type="application/json",
    )
