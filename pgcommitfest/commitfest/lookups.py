from django.http import HttpResponse, Http404
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

import json


@login_required
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
                        "value": "{} ({})".format(u.username, u.get_full_name()),
                    }
                    for u in users
                ],
            }
        ),
        content_type="application/json",
    )
