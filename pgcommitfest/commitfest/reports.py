from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import CommitFest


@login_required
def authorstats(request, cfid):
    cf = get_object_or_404(CommitFest, pk=cfid)
    if not request.user.is_staff:
        raise Http404("Only CF Managers can do that.")

    cursor = connection.cursor()
    cursor.execute(
        """
WITH patches(id,name) AS (
  SELECT p.id, name
   FROM commitfest_patch p
   INNER JOIN commitfest_patchoncommitfest poc ON poc.patch_id=p.id AND poc.commitfest_id=%(cid)s
),
authors(userid, authorpatches) AS (
 SELECT pa.user_id, array_agg(array_to_json(ARRAY[p.id::text, p.name]))
  FROM commitfest_patch_authors pa
  INNER JOIN patches p ON p.id=pa.patch_id
 GROUP BY pa.user_id
),
reviewers(userid, reviewerpatches) AS (
 SELECT pr.user_id, array_agg(array_to_json(ARRAY[p.id::text, p.name]))
  FROM commitfest_patch_reviewers pr
  INNER JOIN patches p ON p.id=pr.patch_id
 GROUP BY pr.user_id
)
SELECT first_name || ' ' || last_name || ' (' || username ||')', authorpatches, reviewerpatches
FROM (authors FULL OUTER JOIN reviewers ON authors.userid=reviewers.userid)
INNER JOIN auth_user u ON u.id=COALESCE(authors.userid, reviewers.userid)
ORDER BY last_name, first_name
""",
        {
            "cid": cf.id,
        },
    )

    return render(
        request,
        "report_authors.html",
        {
            "cf": cf,
            "report": cursor.fetchall(),
            "title": "Author stats",
            "breadcrumbs": [
                {"title": cf.title, "href": "/%s/" % cf.pk},
            ],
        },
    )
