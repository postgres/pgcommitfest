from django.contrib.auth.models import User
from django.db.models import Q
from django.http import Http404, HttpResponse

import json


def userlookup(request):
    query = request.GET.get("query", None)
    if not query:
        raise Http404()

    users = User.objects.filter(
        Q(is_active=True),
        Q(username__icontains=query)
        | Q(first_name__icontains=query)
        | Q(last_name__icontains=query),
    )

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
