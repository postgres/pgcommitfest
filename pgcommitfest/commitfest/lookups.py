from django.contrib.auth.models import User
from django.db import connection
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
        # Filter users to only those who have participated in the specified commitfest.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cpa.user_id FROM commitfest_patch_authors cpa
                INNER JOIN commitfest_patchoncommitfest poc ON poc.patch_id = cpa.patch_id
                WHERE poc.commitfest_id = %(cf)s
                UNION
                SELECT cpr.user_id FROM commitfest_patch_reviewers cpr
                INNER JOIN commitfest_patchoncommitfest poc ON poc.patch_id = cpr.patch_id
                WHERE poc.commitfest_id = %(cf)s
                UNION
                SELECT p.committer_id FROM commitfest_patch p
                INNER JOIN commitfest_patchoncommitfest poc ON poc.patch_id = p.id
                WHERE poc.commitfest_id = %(cf)s AND p.committer_id IS NOT NULL
                """,
                {"cf": cf},
            )
            user_ids = [row[0] for row in cursor.fetchall()]
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
