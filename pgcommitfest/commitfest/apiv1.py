from django.http import (
    HttpResponse,
)

import json
from datetime import date, datetime, timedelta, timezone

from .models import (
    CommitFest,
)


def datetime_serializer(obj):
    if isinstance(obj, date):
        return obj.isoformat()

    if isinstance(obj, datetime):
        return obj.replace(tzinfo=timezone.utc).isoformat()

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


def commitfestst_that_need_ci(request):
    cfs = CommitFest.relevant_commitfests()

    # We continue to run CI on the previous commitfest for a week after it ends
    # to give people some time to move patches over to the next one.
    if cfs["previous"].enddate <= datetime.now(timezone.utc).date() - timedelta(days=7):
        del cfs["previous"]

    del cfs["next_open"]
    del cfs["final"]

    return api_response({"commitfests": cfs})
