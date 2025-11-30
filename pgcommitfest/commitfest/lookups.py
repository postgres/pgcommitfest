from django.contrib.auth.models import User
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseForbidden

import json


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
        # Filter users to only those who have participated in the specified commitfest
        # This includes authors, reviewers, and committers of patches in that commitfest
        users = users.filter(
            Q(patch_author__commitfests__id=cf)
            | Q(patch_reviewer__commitfests__id=cf)
            | Q(committer__patch__commitfests__id=cf)
        ).distinct()

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
