from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import OperationalError, connection, transaction
from django.db.models import Count, Q
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import collections
import functools
import hmac
import json
import urllib
from datetime import datetime, timedelta

from pgcommitfest.mailqueue.util import send_simple_mail
from pgcommitfest.userprofile.models import UserProfile
from pgcommitfest.userprofile.util import UserWrapper

from .ajax import _archivesAPI, doAttachThread, refresh_single_thread
from .feeds import ActivityFeed, calendar
from .forms import (
    BulkEmailForm,
    CommitFestFilterForm,
    NewPatchForm,
    PatchForm,
)
from .models import (
    CfbotBranch,
    CfbotTask,
    CommitFest,
    Committer,
    MailThread,
    Patch,
    PatchHistory,
    PatchOnCommitFest,
    Tag,
    UserInputError,
)

# PostgreSQL SQLSTATEs for transient conflicts that are safe to retry once the
# aborted transaction has been rolled back: serialization_failure and
# deadlock_detected.
RETRYABLE_PGCODES = {"40001", "40P01"}


def retry_on_serialization_failure(view_func):
    """Re-run a view when its transaction hits a serialization failure.

    A few views (home, commitfest) run the whole request at REPEATABLE READ so
    that all of their queries observe a single consistent snapshot. Rendering
    also triggers the lazy, roughly-once-a-month commitfest refresh in
    CommitFest.relevant_commitfests(), which locks and updates rows with
    SELECT ... FOR UPDATE. When two such requests race during a rollover, the
    one that loses the race cannot re-read the newer row under REPEATABLE READ,
    so PostgreSQL aborts it with "could not serialize access due to concurrent
    update" (SQLSTATE 40001) instead of blocking and continuing.

    Once that happens the transaction is dead, so the only way to recover is to
    roll it back and run the view again from scratch. That is why this decorator
    has to sit *outside* transaction.atomic: each attempt then runs in a brand
    new transaction with a fresh snapshot. By the time we retry, the request
    that won the race has already committed the refresh, so the cheap
    up-to-date check short-circuits and the retry neither writes nor conflicts.
    """

    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        except OperationalError as e:
            if getattr(e.__cause__, "pgcode", None) not in RETRYABLE_PGCODES:
                raise
        # A single retry is enough: the refresh only writes once per rollover,
        # so after the winning request commits there is nothing left to
        # conflict with. If the retry fails anyway, something else is going on
        # and we'd rather surface the error than keep hammering the database.
        return view_func(*args, **kwargs)

    return wrapper


def get_tags_data():
    """Generate JSON data for enhanced selectize dropdown with tag colors and descriptions."""
    return json.dumps(
        [
            {
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "description": tag.description,
            }
            for tag in Tag.objects.all().order_by("name")
        ]
    )


@retry_on_serialization_failure
@transaction.atomic
def home(request):
    curs = connection.cursor()
    # Make sure the that all the queries work on the same snapshot. Needs to be
    # first in the transaction.atomic decorator.
    curs.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

    cfs = CommitFest.relevant_commitfests()

    context = {
        "cfs": cfs,
        "header_activity": "Activity log",
        "header_activity_link": "/activity/",
    }

    # Add dashboard content for logged-in users
    if request.user.is_authenticated:
        # Check if user is experienced (has been active for a while)

        # Consider user experienced if they joined more than 30 days ago
        is_experienced_user = request.user.date_joined < timezone.now() - timedelta(
            days=30
        )

        curs = connection.cursor()
        curs.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

        # Use existing cfs data instead of querying again
        cf = cfs.get("in_progress") or cfs.get("open")

        form = CommitFestFilterForm(request.GET, commitfest=cf)
        patch_list = patchlist(request, cf, personalized=True)

        if patch_list.redirect:
            return patch_list.redirect

        # Get stats related to user for current commitfest (same as me() view)
        curs.execute(
            """SELECT
                ps.status, ps.statusstring, count(*)
            FROM commitfest_patchoncommitfest poc
            INNER JOIN commitfest_patch p ON p.id = poc.patch_id
            INNER JOIN commitfest_patchstatus ps ON ps.status=poc.status
            WHERE
                ps.status = ANY(%(openstatuses)s)
            AND (
                EXISTS (
                    SELECT 1 FROM commitfest_patch_reviewers cpr WHERE cpr.patch_id=p.id AND cpr.user_id=%(user_id)s
                )
                OR EXISTS (
                    SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id AND cpa.user_id=%(user_id)s
                )
                OR p.committer_id=%(user_id)s
            )
            GROUP BY ps.status ORDER BY ps.sortkey""",
            {
                "user_id": request.user.id,
                "openstatuses": PatchOnCommitFest.OPEN_STATUSES,
            },
        )
        statussummary = curs.fetchall()

        context.update(
            {
                "show_dashboard": True,
                "form": form,
                "patches": patch_list.patches,
                "statussummary": statussummary,
                "tags_data": get_tags_data(),
                "all_tags": {t.id: t for t in Tag.objects.all()},
                "has_filter": patch_list.has_filter,
                "grouping": patch_list.sortkey == 0,
                "sortkey": patch_list.sortkey,
                "openpatchids": [p["id"] for p in patch_list.patches if p["is_open"]],
                "userprofile": getattr(request.user, "userprofile", UserProfile()),
                "is_experienced_user": is_experienced_user,
            }
        )

    return render(request, "home.html", context)


@login_required
def me_legacy_redirect(request):
    # Previously we would have a dedicated dashboard page, now this
    # is on the homepage.
    return HttpResponseRedirect("/#dashboard")


def commitfest_history_legacy_redirect(request):
    # For a while the list of all commitfests lived here, next to an unsorted
    # duplicate at /archive/. The two were merged under /archive/ since that's
    # the shorter URL, but links to this one should keep working.
    return HttpResponsePermanentRedirect("/archive/")


def archive(request):
    cfs = list(CommitFest.objects.order_by("-enddate"))

    return render(
        request,
        "archive.html",
        {
            "commitfests": cfs,
            "title": "Commitfest history",
            "header_activity": "Activity log",
            "header_activity_link": "/activity/",
        },
    )


def help(request):
    return render(
        request,
        "help.html",
        {
            "title": "What is the Commitfest app?",
            "auto_move_email_activity_days": settings.AUTO_MOVE_EMAIL_ACTIVITY_DAYS,
            "auto_move_max_failing_days": settings.AUTO_MOVE_MAX_FAILING_DAYS,
        },
    )


def commitfests_ics(_: HttpRequest) -> HttpResponse:
    """
    Calendar feed of all non-draft commitfests in iCalendar format (RFC 5545).
    """
    commitfests = CommitFest.objects.filter(draft=False).order_by("startdate")

    response = HttpResponse(
        calendar(commitfests).to_ical(), content_type="text/calendar; charset=utf-8"
    )
    response["Content-Disposition"] = 'inline; filename="commitfests.ics"'
    return response


def activity(request, cfid=None, rss=None):
    # Number of notes to fetch
    if rss:
        num = 50
    else:
        num = 100

    if cfid:
        cf = get_object_or_404(CommitFest, pk=cfid)

        # Yes, we do string concatenation of the were clause. Because
        # we're evil.  And also because the number has been verified
        # when looking up the cf itself, so nothing can be injected
        # there.
        where = "WHERE EXISTS (SELECT 1 FROM commitfest_patchoncommitfest poc2 WHERE poc2.patch_id=p.id AND poc2.commitfest_id={0})".format(
            cf.id
        )
    else:
        cf = None
        where = ""

    sql = "SELECT ph.date, auth_user.username AS by, ph.what, p.id AS patchid, p.name, (SELECT max(commitfest_id) FROM commitfest_patchoncommitfest poc WHERE poc.patch_id=p.id) AS cfid FROM commitfest_patchhistory ph INNER JOIN commitfest_patch p ON ph.patch_id=p.id INNER JOIN auth_user on auth_user.id=ph.by_id {0} ORDER BY ph.date DESC LIMIT {1}".format(
        where, num
    )

    curs = connection.cursor()
    curs.execute(sql)
    activity = [dict(zip([c[0] for c in curs.description], r)) for r in curs.fetchall()]

    if rss:
        # Return RSS feed with these objects
        return ActivityFeed(activity, cf)(request)
    else:
        # Return regular webpage
        return render(
            request,
            "activity.html",
            {
                "commitfest": cf,
                "activity": activity,
                "title": cf and "Commitfest activity" or "Global Commitfest activity",
                "rss_alternate": cf
                and "/{0}/activity.rss/".format(cf.id)
                or "/activity.rss/",
                "rss_alternate_title": "PostgreSQL Commitfest Activity Log",
                "breadcrumbs": cf
                and [
                    {"title": cf.title, "href": "/%s/" % cf.pk},
                ]
                or None,
            },
        )


def redir(request, what, end):
    if what == "open":
        cfs = list(
            CommitFest.objects.filter(status=CommitFest.STATUS_OPEN, draft=False)
        )
    elif what == "inprogress":
        cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_INPROGRESS))
    elif what == "current":
        cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_INPROGRESS))
        if len(cfs) == 0:
            cfs = list(
                CommitFest.objects.filter(status=CommitFest.STATUS_OPEN, draft=False)
            )
    elif what == "draft":
        cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_OPEN, draft=True))
    else:
        raise Http404()

    if len(cfs) == 0:
        messages.warning(
            request, "No {0} commitfests exist, redirecting to startpage.".format(what)
        )
        return HttpResponseRedirect("/")
    if len(cfs) != 1:
        messages.warning(
            request,
            "More than one {0} commitfest exists, redirecting to startpage instead.".format(
                what
            ),
        )
        return HttpResponseRedirect("/")

    query_string = request.GET.urlencode()
    if query_string:
        query_string = "?" + query_string
    return HttpResponseRedirect(f"/{cfs[0].id}/{end}{query_string}")


PatchList = collections.namedtuple(
    "PatchList", ["patches", "has_filter", "sortkey", "redirect"]
)


def patchlist(request, cf, personalized=False):
    # Build a dynamic filter based on the filtering options entered
    whereclauses = []
    whereparams = {}

    if request.GET.get("status", "-1") != "-1":
        try:
            whereparams["status"] = int(request.GET["status"])
            whereclauses.append("poc.status=%(status)s")
        except ValueError:
            # int() failed -- so just ignore this filter
            pass

    if request.GET.get("targetversion", "-1") != "-1":
        if request.GET["targetversion"] == "-2":
            whereclauses.append("targetversion_id IS NULL")
        else:
            try:
                whereparams["verid"] = int(request.GET["targetversion"])
                whereclauses.append("targetversion_id=%(verid)s")
            except ValueError:
                # int() failed, ignore
                pass

    if request.GET.getlist("tag") != []:
        try:
            tag_ids = [int(t) for t in request.GET.getlist("tag")]
            for tag_id in tag_ids:
                # Instead of using parameters, we just inline the tag_id. This
                # is easier because we have can have multiple tags, and since
                # tag_id is always an int it's safe with respect to SQL
                # injection.
                whereclauses.append(
                    f"EXISTS (SELECT 1 FROM commitfest_patch_tags tags WHERE tags.patch_id=p.id AND tags.tag_id={tag_id})"
                )
        except ValueError:
            # int() failed -- so just ignore this filter
            pass

    if request.GET.get("author", "-1") != "-1":
        if request.GET["author"] == "-2":
            whereclauses.append(
                "NOT EXISTS (SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id)"
            )
        elif request.GET["author"] == "-3":
            # Checking for "yourself" requires the user to be logged in!
            if not request.user.is_authenticated:
                return PatchList(
                    patches=[],
                    has_filter=False,
                    sortkey=0,
                    redirect=HttpResponseRedirect(
                        "%s?next=%s" % (settings.LOGIN_URL, request.path)
                    ),
                )
            whereclauses.append(
                "EXISTS (SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id AND cpa.user_id=%(self)s)"
            )
            whereparams["self"] = request.user.id
        else:
            try:
                whereparams["author"] = int(request.GET["author"])
                whereclauses.append(
                    "EXISTS (SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id AND cpa.user_id=%(author)s)"
                )
            except ValueError:
                # int() failed -- so just ignore this filter
                pass

    if request.GET.get("reviewer", "-1") != "-1":
        if request.GET["reviewer"] == "-2":
            whereclauses.append(
                "NOT EXISTS (SELECT 1 FROM commitfest_patch_reviewers cpr WHERE cpr.patch_id=p.id)"
            )
        elif request.GET["reviewer"] == "-3":
            # Checking for "yourself" requires the user to be logged in!
            if not request.user.is_authenticated:
                return PatchList(
                    patches=[],
                    has_filter=False,
                    sortkey=0,
                    redirect=HttpResponseRedirect(
                        "%s?next=%s" % (settings.LOGIN_URL, request.path)
                    ),
                )
            whereclauses.append(
                "EXISTS (SELECT 1 FROM commitfest_patch_reviewers cpr WHERE cpr.patch_id=p.id AND cpr.user_id=%(self)s)"
            )
            whereparams["self"] = request.user.id
        else:
            try:
                whereparams["reviewer"] = int(request.GET["reviewer"])
                whereclauses.append(
                    "EXISTS (SELECT 1 FROM commitfest_patch_reviewers cpr WHERE cpr.patch_id=p.id AND cpr.user_id=%(reviewer)s)"
                )
            except ValueError:
                # int() failed -- so just ignore this filter
                pass

    if request.GET.get("text", "") != "":
        whereclauses.append("p.name ILIKE '%%' || %(txt)s || '%%'")
        whereparams["txt"] = request.GET["text"]

    has_filter = len(whereclauses) > 0

    if personalized:
        whereclauses.append("""
            EXISTS (
                SELECT 1 FROM commitfest_patch_reviewers cpr WHERE cpr.patch_id=p.id AND cpr.user_id=%(self)s
            ) OR EXISTS (
                SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id AND cpa.user_id=%(self)s
            ) OR p.committer_id=%(self)s""")
        whereparams["self"] = request.user.id

        whereclauses.append("poc.status=ANY(%(openstatuses)s)")
    else:
        whereclauses.append("poc.commitfest_id=%(cid)s")
        # Exclude "Moved to other CF" patches from draft commitfests
        if cf.draft:
            whereclauses.append("poc.status != %(status_moved)s")
            whereparams["status_moved"] = PatchOnCommitFest.STATUS_MOVED

    if personalized:
        # For now we can just order by these names in descending order, because
        # they are crafted such that they alphabetically sort in the intended
        # order.
        columns_str = """
            CASE WHEN
                EXISTS (
                    SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id AND cpa.user_id=%(self)s
                ) AND (
                    cf.status = %(closed_status)s
                )
            THEN 'Your still open patches in a closed commitfest (you should move or close these)'
            WHEN
                EXISTS (
                    SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id AND cpa.user_id=%(self)s
                ) AND (
                    poc.status=%(needs_author)s
                    OR (branch.needs_rebase_since IS NOT NULL AND poc.status=ANY(%(open_statuses)s))
                    OR branch.failing_since + interval '4 days' < now()
                    OR (%(is_committer)s AND poc.status=%(needs_committer)s)
                )
            THEN 'Your patches that need changes from you'
            WHEN
                NOT EXISTS (
                    SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id AND cpa.user_id=%(self)s
                ) AND (
                    poc.status=ANY(%(review_statuses)s)
                )
            THEN 'Patches that are ready for your review'
            ELSE 'Blocked on others'
            END AS group_name,
            cf.id AS cf_id,
            cf.name AS cf_name,
            cf.status AS cf_status,
        """
        whereparams["needs_author"] = PatchOnCommitFest.STATUS_AUTHOR
        whereparams["needs_committer"] = PatchOnCommitFest.STATUS_COMMITTER
        whereparams["open_statuses"] = PatchOnCommitFest.OPEN_STATUSES
        whereparams["closed_status"] = CommitFest.STATUS_CLOSED
        is_committer = bool(Committer.objects.filter(user=request.user, active=True))
        whereparams["is_committer"] = is_committer

        if is_committer:
            whereparams["review_statuses"] = [
                PatchOnCommitFest.STATUS_REVIEW,
                PatchOnCommitFest.STATUS_COMMITTER,
            ]
        else:
            whereparams["review_statuses"] = [
                PatchOnCommitFest.STATUS_REVIEW,
            ]
        joins_str = "INNER JOIN commitfest_commitfest cf ON poc.commitfest_id=cf.id"
        groupby_str = "cf.id,"
    else:
        columns_str = ""
        joins_str = ""
        groupby_str = ""

    # Figure out custom ordering
    try:
        sortkey = int(request.GET.get("sortkey", "0"))
    except ValueError:
        sortkey = 0

    if sortkey == 2:
        orderby_str = "lastmail, created"
    elif sortkey == -2:
        orderby_str = "lastmail DESC, created DESC"
    elif sortkey == 3:
        orderby_str = "num_cfs DESC, modified, created"
    elif sortkey == -3:
        orderby_str = "num_cfs ASC, modified DESC, created DESC"
    elif sortkey == 4:
        orderby_str = "p.id"
    elif sortkey == -4:
        orderby_str = "p.id DESC"
    elif sortkey == 5:
        orderby_str = "p.name, created"
    elif sortkey == -5:
        orderby_str = "p.name DESC, created DESC"
    elif sortkey == 6:
        orderby_str = "branch.all_additions + branch.all_deletions NULLS LAST, created"
    elif sortkey == -6:
        orderby_str = (
            "branch.all_additions + branch.all_deletions DESC NULLS LAST, created DESC"
        )
    elif sortkey == 7:
        orderby_str = "branch.failing_since DESC NULLS FIRST, branch.created DESC"
    elif sortkey == -7:
        orderby_str = "branch.failing_since NULLS LAST, branch.created"
    elif sortkey == 8:
        orderby_str = "poc.commitfest_id, lastmail DESC"
    elif sortkey == -8:
        orderby_str = "poc.commitfest_id DESC, lastmail"
    elif sortkey == 9 and not personalized:
        # PostgreSQL sorts NULLs last when ascending and first when
        # descending, so patches without a committer end up at the bottom in
        # this order and at the top in the reverse one.
        orderby_str = (
            "committer.last_name, committer.first_name, committer.username, p.id"
        )
    elif sortkey == -9 and not personalized:
        orderby_str = (
            "committer.last_name DESC, committer.first_name DESC, "
            "committer.username DESC, p.id DESC"
        )
    else:
        if personalized:
            # First we sort by group_name, to have the grouping work.
            # Then we show non-failing patches first, and the ones that are
            # shortest failing we show first. We consider patches in a closed
            # commitfest, as if they are failing since that commitfest was
            # closed.
            # Then we sort by start date of the CF, to show entries in the "In
            # progress" commitfest before ones in the "Open" commitfest.
            # And then to break ties, we put ones with the most recent email at
            # the top.
            orderby_str = """group_name DESC,
                COALESCE(
                    branch.failing_since,
                    CASE WHEN cf.status = %(cf_closed_status)s
                    THEN enddate ELSE NULL END
                ) DESC NULLS FIRST,
                cf.startdate,
                lastmail DESC"""
            whereparams["cf_closed_status"] = CommitFest.STATUS_CLOSED
        else:
            orderby_str = "created"
        sortkey = 0

    if not has_filter and sortkey == 0 and request.GET:
        # Redirect to get rid of the ugly url
        return PatchList(
            patches=[],
            has_filter=False,
            sortkey=0,
            redirect=HttpResponseRedirect(request.path),
        )

    if whereclauses:
        where_str = "({0})".format(") AND (".join(whereclauses))
    else:
        where_str = "true"
    params = {
        "openstatuses": PatchOnCommitFest.OPEN_STATUSES,
        "cid": cf.id,
    }
    params.update(whereparams)

    # Let's not overload the poor django ORM
    curs = connection.cursor()
    curs.execute(
        f"""SELECT p.id, p.name, poc.status, v.version AS targetversion, p.created, p.modified, p.lastmail, committer.first_name || ' ' || committer.last_name || ' (' || committer.username || ')' AS committer,
        {columns_str}
(poc.status=ANY(%(openstatuses)s)) AS is_open,
(SELECT string_agg(first_name || ' ' || last_name || ' (' || username || ')', ', ') FROM auth_user INNER JOIN commitfest_patch_authors cpa ON cpa.user_id=auth_user.id WHERE cpa.patch_id=p.id) AS author_names,
(SELECT string_agg(first_name || ' ' || last_name || ' (' || username || ')', ', ') FROM auth_user INNER JOIN commitfest_patch_reviewers cpr ON cpr.user_id=auth_user.id WHERE cpr.patch_id=p.id) AS reviewer_names,
(SELECT count(1) FROM commitfest_patchoncommitfest pcf WHERE pcf.patch_id=p.id) AS num_cfs,
(SELECT array_agg(tag_id) FROM commitfest_patch_tags t WHERE t.patch_id=p.id) AS tag_ids,

branch.needs_rebase_since,
branch.failing_since,
(
    SELECT row_to_json(t) as cfbot_results
    from (
        SELECT
            count(*) FILTER (WHERE task.status in ('COMPLETED', 'PAUSED')) as completed,
            count(*) FILTER (WHERE task.status in ('CREATED', 'SCHEDULED', 'EXECUTING')) running,
            count(*) FILTER (WHERE task.status in ('ABORTED', 'ERRORED', 'FAILED')) failed,
            count(*) FILTER (WHERE task.status in ('ABORTED', 'ERRORED', 'FAILED') AND task.task_name != 'FormattingCheck') as failed_non_formatting,
            count(*) total,
            string_agg(task.task_name, ', ') FILTER (WHERE task.status in ('ABORTED', 'ERRORED', 'FAILED')) as failed_task_names,
            branch.status as branch_status,
            branch.apply_url,
            branch.build_url,
            branch.patch_count,
            branch.all_additions,
            branch.all_deletions
        FROM commitfest_cfbotbranch branch
        LEFT JOIN commitfest_cfbottask task ON task.branch_id = branch.branch_id
        WHERE branch.patch_id=p.id
        GROUP BY branch.patch_id
    ) t
)
FROM commitfest_patch p
INNER JOIN commitfest_patchoncommitfest poc ON poc.patch_id=p.id
{joins_str}
LEFT JOIN auth_user committer ON committer.id=p.committer_id
LEFT JOIN commitfest_targetversion v ON p.targetversion_id=v.id
LEFT JOIN commitfest_cfbotbranch branch ON branch.patch_id=p.id
WHERE {where_str}
GROUP BY p.id, poc.id, {groupby_str} committer.id, v.version, branch.patch_id
ORDER BY is_open DESC, {orderby_str}""",
        params,
    )
    patches = [
        dict(zip([col[0] for col in curs.description], row)) for row in curs.fetchall()
    ]
    return PatchList(
        patches=patches,
        sortkey=sortkey,
        has_filter=has_filter,
        redirect=False,
    )


@retry_on_serialization_failure
@transaction.atomic
def commitfest(request, cfid):
    curs = connection.cursor()
    # Make sure the patchlist() query, the stats query and, Tag.objects.all()
    # all work on the same snapshot. Needs to be first in the
    # transaction.atomic decorator.
    curs.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    # Find ourselves
    cf = get_object_or_404(CommitFest, pk=cfid)

    patch_list = patchlist(request, cf)
    if patch_list.redirect:
        return patch_list.redirect

    # Generate patch status summary.
    # Exclude "Moved to other CF" status from draft commitfests
    status_filter = "AND poc.status != %(status_moved)s" if cf.draft else ""
    curs.execute(
        f"SELECT ps.status, ps.statusstring, count(*) FROM commitfest_patchoncommitfest poc INNER JOIN commitfest_patchstatus ps ON ps.status=poc.status WHERE commitfest_id=%(id)s {status_filter} GROUP BY ps.status ORDER BY ps.sortkey",
        {
            "id": cf.id,
            "status_moved": PatchOnCommitFest.STATUS_MOVED,
        },
    )
    statussummary = curs.fetchall()
    statussummary.append([-1, "Total", sum((r[2] for r in statussummary))])

    # Generates a fairly expensive query, which we shouldn't do unless
    # the user is logged in. XXX: Figure out how to avoid doing that..
    form = CommitFestFilterForm(request.GET, commitfest=cf)

    return render(
        request,
        "commitfest.html",
        {
            "cf": cf,
            "form": form,
            "patches": patch_list.patches,
            "statussummary": statussummary,
            "tags_data": get_tags_data(),
            "all_tags": {t.id: t for t in Tag.objects.all()},
            "has_filter": patch_list.has_filter,
            "title": f"{cf.title} ({cf.periodstring})",
            "sortkey": patch_list.sortkey,
            "openpatchids": [p["id"] for p in patch_list.patches if p["is_open"]],
            "header_activity": "Activity log",
            "header_activity_link": "activity/",
            "userprofile": getattr(request.user, "userprofile", UserProfile()),
        },
    )


def patches_by_messageid(messageid):
    # First try to find the messageid in our database
    patches = (
        Patch.objects.select_related()
        .filter(mailthread_set__messageid=messageid)
        .order_by(
            "created",
        )
        .all()
    )
    if patches:
        return patches

    urlsafe_messageid = urllib.parse.quote(messageid)

    # If it's not there, try to find it in the archives
    try:
        thread = _archivesAPI(f"/message-id.json/{urlsafe_messageid}")
    except Http404:
        return []

    if len(thread) == 0:
        return []

    first_email = min(thread, key=lambda x: x["date"])

    return (
        Patch.objects.select_related()
        .filter(mailthread_set__messageid=first_email["msgid"])
        .order_by(
            "created",
        )
        .all()
    )


# We require login for this page primarily so that the author/reviewer filter
# boxes can always be searched. Since searching for users outside of a
# commitfest requires users to be logged in to not make the data too easy to
# scrape.
@login_required
def global_search(request):
    if "searchterm" not in request.GET:
        return HttpResponseRedirect("/")
    searchterm = request.GET["searchterm"].strip()
    patches = []

    if "@" in searchterm:
        # This is probably a messageid, so let's try to look up patches related
        # to it. Let's first remove any < and > around it though.
        cleaned_id = searchterm.removeprefix("<").removesuffix(">")
        patches = patches_by_messageid(cleaned_id)

    if not patches:
        patches_query = (
            Patch.objects.select_related("targetversion", "committer")
            .prefetch_related(
                "authors",
                "reviewers",
                "tags",
                "patchoncommitfest_set__commitfest",
                "mailthread_set",
            )
            .select_related("cfbot_branch")
            .filter(name__icontains=searchterm)
        )

        # Apply filters using the same logic as patchlist
        if request.GET.get("status", "-1") != "-1":
            try:
                status = int(request.GET["status"])
                patches_query = patches_query.filter(
                    patchoncommitfest__status=status
                ).distinct()
            except ValueError:
                pass

        if request.GET.get("targetversion", "-1") != "-1":
            if request.GET["targetversion"] == "-2":
                patches_query = patches_query.filter(targetversion_id__isnull=True)
            else:
                try:
                    ver_id = int(request.GET["targetversion"])
                    patches_query = patches_query.filter(targetversion_id=ver_id)
                except ValueError:
                    pass

        if request.GET.getlist("tag"):
            try:
                tag_ids = [int(t) for t in request.GET.getlist("tag")]
                for tag_id in tag_ids:
                    patches_query = patches_query.filter(tags__id=tag_id)
                patches_query = patches_query.distinct()
            except ValueError:
                pass

        # Apply author filter
        if request.GET.get("author", "-1") != "-1":
            if request.GET["author"] == "-2":
                patches_query = patches_query.filter(authors__isnull=True)
            elif request.GET["author"] == "-3":
                # Filter for current user's patches
                if not request.user.is_authenticated:
                    return HttpResponseRedirect(
                        f"{settings.LOGIN_URL}?next={request.path}?searchterm={searchterm}"
                    )
                patches_query = patches_query.filter(authors=request.user)
            else:
                try:
                    author_id = int(request.GET["author"])
                    patches_query = patches_query.filter(authors__id=author_id)
                except ValueError:
                    pass

        # Apply reviewer filter
        if request.GET.get("reviewer", "-1") != "-1":
            if request.GET["reviewer"] == "-2":
                patches_query = patches_query.filter(reviewers__isnull=True)
            elif request.GET["reviewer"] == "-3":
                # Filter for current user's reviews
                if not request.user.is_authenticated:
                    return HttpResponseRedirect(
                        f"{settings.LOGIN_URL}?next={request.path}?searchterm={searchterm}"
                    )
                patches_query = patches_query.filter(reviewers=request.user)
            else:
                try:
                    reviewer_id = int(request.GET["reviewer"])
                    patches_query = patches_query.filter(reviewers__id=reviewer_id)
                except ValueError:
                    pass

        # Ensure distinct results after filtering on many-to-many relationships
        patches_query = patches_query.distinct()

        # Apply sorting based on sortkey parameter (adapted for Django ORM)
        sortkey = request.GET.get("sortkey", "1")
        if sortkey == "2":  # Latest mail
            patches_query = patches_query.order_by("-modified")  # Use modified as proxy
        elif sortkey == "-2":
            patches_query = patches_query.order_by("modified")
        elif sortkey == "3":  # Num cfs
            patches_query = patches_query.annotate(
                num_cfs=Count("patchoncommitfest")
            ).order_by("-num_cfs")
        elif sortkey == "-3":
            patches_query = patches_query.annotate(
                num_cfs=Count("patchoncommitfest")
            ).order_by("num_cfs")
        elif sortkey == "4":  # ID
            patches_query = patches_query.order_by("id")
        elif sortkey == "-4":
            patches_query = patches_query.order_by("-id")
        elif sortkey == "5":  # Patch name
            patches_query = patches_query.order_by("name")
        elif sortkey == "-5":
            patches_query = patches_query.order_by("-name")
        elif sortkey == "8":  # CF
            patches_query = patches_query.order_by("patchoncommitfest__commitfest__id")
        elif sortkey == "-8":
            patches_query = patches_query.order_by("-patchoncommitfest__commitfest__id")
        else:  # Default: Created (sortkey 1)
            patches_query = patches_query.order_by("created")

        patches = patches_query.all()

    if len(patches) == 1:
        patch = patches[0]
        return HttpResponseRedirect(f"/patch/{patch.id}/")

    # Use the existing filter form (no cf parameter, will require login for user lookups)
    form = CommitFestFilterForm(request.GET)

    # Get user profile for timestamp preferences
    userprofile = None
    if request.user.is_authenticated:
        try:
            from pgcommitfest.userprofile.models import UserProfile

            userprofile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            pass

    return render(
        request,
        "patchsearch.html",
        {
            "patches": patches,
            "title": "Patch search results",
            "searchterm": searchterm,
            "form": form,
            "cf": None,  # No specific commitfest context
            "sortkey": int(request.GET.get("sortkey") or "1"),
            "tags_data": get_tags_data(),
            "all_tags": {t.id: t for t in Tag.objects.all()},
            "userprofile": userprofile,
        },
    )


def patch_legacy_redirect(request, cfid, patchid):
    # Previously we would include the commitfest id in the URL. This is no
    # longer the case.
    return HttpResponseRedirect(f"/patch/{patchid}/")


def patch(request, patchid):
    patch = get_object_or_404(Patch.objects.select_related(), pk=patchid)

    patch_commitfests = (
        PatchOnCommitFest.objects.select_related("commitfest")
        .filter(patch=patch)
        .order_by("-enterdate")
        .all()
    )
    cf = patch_commitfests[0].commitfest

    committers = Committer.objects.filter(active=True).order_by(
        "user__first_name", "user__last_name"
    )

    cfbot_branch = getattr(patch, "cfbot_branch", None)
    cfbot_tasks = patch.cfbot_tasks.order_by("position") if cfbot_branch else []

    # XXX: this creates a session, so find a smarter way. Probably handle
    # it in the callback and just ask the user then?
    if request.user.is_authenticated:
        committer = [c for c in committers if c.user == request.user]
        if len(committer) > 0:
            is_committer = True
            is_this_committer = committer[0] == patch.committer
        else:
            is_committer = is_this_committer = False

        is_reviewer = request.user in patch.reviewers.all()
        is_subscribed = patch.subscribers.filter(id=request.user.id).exists()
    else:
        is_committer = False
        is_this_committer = False
        is_reviewer = False
        is_subscribed = False

    return render(
        request,
        "patch.html",
        {
            "cf": cf,
            "patch": patch,
            "patch_commitfests": patch_commitfests,
            "cfbot_branch": cfbot_branch,
            "cfbot_tasks": cfbot_tasks,
            "is_committer": is_committer,
            "is_this_committer": is_this_committer,
            "is_reviewer": is_reviewer,
            "is_subscribed": is_subscribed,
            "committers": committers,
            "attachnow": "attachthreadnow" in request.GET,
            "title": patch.name,
            "description": (
                "PostgreSQL patch by %s in the %s commitfest."
                % (patch.authors_string or "unknown author", cf.title)
            ),
            "breadcrumbs": [
                {"title": cf.title, "href": "/%s/" % cf.pk},
            ],
            "userprofile": getattr(request.user, "userprofile", UserProfile()),
            "cfs": CommitFest.relevant_commitfests(),
        },
    )


@login_required
@transaction.atomic
def patchform(request, patchid):
    patch = get_object_or_404(Patch, pk=patchid)
    cf = patch.current_commitfest()

    prevreviewers = list(patch.reviewers.all())
    prevauthors = list(patch.authors.all())
    prevcommitter = patch.committer

    if request.method == "POST":
        form = PatchForm(data=request.POST, instance=patch)
        if form.is_valid():
            # Some fields need to be set when creating a new one
            r = form.save(commit=False)
            # Fill out any locked fields here

            form.save_m2m()

            # Track all changes
            for field, values in r.diff.items():
                if field == "tags":
                    value = ", ".join(v.name for v in values[1])
                else:
                    value = values[1]
                PatchHistory(
                    patch=patch,
                    by=request.user,
                    what="Changed %s to %s" % (field, value),
                ).save_and_notify(
                    prevcommitter=prevcommitter,
                    prevreviewers=prevreviewers,
                    prevauthors=prevauthors,
                )
            r.set_modified()
            r.save()
            return HttpResponseRedirect("../../%s/" % r.pk)
        # Else fall through and render the page again
    else:
        form = PatchForm(instance=patch)

    return render(
        request,
        "base_form.html",
        {
            "cf": cf,
            "form": form,
            "patch": patch,
            "title": "Edit patch",
            "tags_data": get_tags_data(),
            "breadcrumbs": [
                {"title": cf.title, "href": "/%s/" % cf.pk},
                {"title": "View patch", "href": "/%s/%s/" % (cf.pk, patch.pk)},
            ],
        },
    )


class ThreadAttachFailed(Exception):
    pass


@login_required
def newpatch(request, cfid):
    cf = get_object_or_404(CommitFest, pk=cfid)
    if not cf.status == CommitFest.STATUS_OPEN and not request.user.is_staff:
        raise Http404("This commitfest is not open!")

    if request.method == "POST":
        form = NewPatchForm(data=request.POST)
        if form.is_valid():
            # A failure to attach the thread is re-raised as
            # ThreadAttachFailed so that it still propagates out of the
            # atomic block, which rolls back the patch and everything else
            # created here. The form error is only set after leaving the
            # block, so the queries needed to re-render the form still work
            # even if the failure was a database error that aborted the
            # transaction. Failures in the other statements are not caught
            # here, so they still result in a logged 500.
            try:
                with transaction.atomic():
                    patch = form.save()
                    PatchOnCommitFest(
                        patch=patch, commitfest=cf, enterdate=datetime.now()
                    ).save()
                    PatchHistory(
                        patch=patch, by=request.user, what="Created patch record"
                    ).save()
                    try:
                        doAttachThread(
                            cf, patch, form.cleaned_data["threadmsgid"], request.user
                        )
                    except Http404 as e:
                        # This is a horrible breakage of API layers
                        raise ThreadAttachFailed(
                            "Selected thread did not exist in the archives"
                        ) from e
                    except Exception as e:
                        raise ThreadAttachFailed(
                            "An error occurred looking up the thread in the archives."
                        ) from e
                return HttpResponseRedirect("/patch/%s/" % (patch.id,))
            except ThreadAttachFailed as e:
                form._errors["threadmsgid"] = form.error_class((str(e),))
    else:
        form = NewPatchForm(request=request)

    return render(
        request,
        "base_form.html",
        {
            "form": form,
            "title": "New patch",
            "tags_data": get_tags_data(),
            "breadcrumbs": [
                {"title": f"{cf.title} ({cf.periodstring})", "href": "/%s/" % cf.pk},
            ],
            "savebutton": "Create patch",
            "threadbrowse": True,
        },
    )


@require_POST
@login_required
@transaction.atomic
def status(request, patchid, status):
    patch = get_object_or_404(Patch.objects.select_related(), pk=patchid)
    cf = patch.current_commitfest()
    poc = get_object_or_404(
        PatchOnCommitFest.objects.select_related(),
        commitfest__id=cf.id,
        patch__id=patchid,
    )

    status_mapping = {
        "review": PatchOnCommitFest.STATUS_REVIEW,
        "author": PatchOnCommitFest.STATUS_AUTHOR,
        "committer": PatchOnCommitFest.STATUS_COMMITTER,
    }

    new_status = status_mapping[status]

    if new_status != poc.status:
        poc.set_status(new_status)
        PatchHistory(
            patch=poc.patch, by=request.user, what="New status: %s" % poc.statusstring
        ).save_and_notify()

    return HttpResponseRedirect("/patch/%s/" % (poc.patch.id))


@require_POST
@login_required
@transaction.atomic
def close(request, patchid, status):
    if status == "next":
        raise Exception("Can't happen, use transition/ endpoint")

    patch = get_object_or_404(Patch.objects.select_related(), pk=patchid)
    cf = patch.current_commitfest()

    try:
        request_cfid = int(request.GET.get("cfid", ""))
    except ValueError:
        # int() failed, ignore
        request_cfid = None

    if request_cfid is not None and request_cfid != cf.id:
        # The cfid parameter is only added to the /next/ link. That's the only
        # close operation where two people pressing the button at the same time
        # can have unintended effects.
        messages.error(
            request,
            "The patch was moved to a new commitfest by someone else. Please double check if you still want to retry this operation.",
        )
        return HttpResponseRedirect(f"/patch/{patch.id}/")

    poc = get_object_or_404(
        PatchOnCommitFest.objects.select_related(),
        commitfest__id=cf.id,
        patch__id=patchid,
    )

    if status == "committed":
        if poc.commitfest.is_open:
            # Needs to be done before the next if condition, so the committer
            # that's set there is set on the correct poc.
            #
            # A patch that was already closed (e.g. returned with feedback)
            # might still get committed later, and then it should also end up
            # in the commitfest it was committed in.
            in_progress_cf = CommitFest.get_in_progress()
            if in_progress_cf is not None:
                poc = patch.move(
                    poc.commitfest,
                    in_progress_cf,
                    request.user,
                    allow_move_to_in_progress=True,
                    allow_move_closed=True,
                )
            elif poc.commitfest.draft:
                open_cf = CommitFest.get_open_regular()
                poc = patch.move(
                    poc.commitfest,
                    open_cf,
                    request.user,
                    allow_move_closed=True,
                )

        committer_username = request.GET.get("c")
        if committer_username is None:
            messages.error(request, "No committer specified.")
            return HttpResponseRedirect(f"/patch/{patchid}/")
        committer = get_object_or_404(Committer, user__username=committer_username)
        if committer != poc.patch.committer:
            # Committer changed!
            prevcommitter = poc.patch.committer
            poc.patch.committer = committer
            PatchHistory(
                patch=poc.patch,
                by=request.user,
                what="Changed committer to %s" % committer,
            ).save_and_notify(prevcommitter=prevcommitter)

        poc.status = PatchOnCommitFest.STATUS_COMMITTED

    status_mapping = {
        "reject": PatchOnCommitFest.STATUS_REJECTED,
        "withdrawn": PatchOnCommitFest.STATUS_WITHDRAWN,
        "feedback": PatchOnCommitFest.STATUS_RETURNED,
        "committed": PatchOnCommitFest.STATUS_COMMITTED,
    }
    new_status = status_mapping[status]
    poc.set_status(new_status)

    # Clear needs_rebase_since if patch is being closed (all closed statuses)
    if new_status not in PatchOnCommitFest.OPEN_STATUSES:
        try:
            cfbot_branch = poc.patch.cfbot_branch
            if cfbot_branch.needs_rebase_since:
                cfbot_branch.needs_rebase_since = None
                cfbot_branch.save()
        except CfbotBranch.DoesNotExist:
            pass

    PatchHistory(
        patch=poc.patch,
        by=request.user,
        what="Closed in commitfest %s with status: %s"
        % (poc.commitfest, poc.statusstring),
    ).save_and_notify()

    return HttpResponseRedirect(f"/patch/{patchid}")


def int_param_or_none(request, param):
    """Helper function to convert a string to an int or return None."""
    try:
        return int(request.GET.get(param, ""))
    except ValueError:
        return None


@require_POST
@login_required
@transaction.atomic
def move(request, patchid):
    from_cf_id = int_param_or_none(request, "from_cf_id")
    to_cf_id = int_param_or_none(request, "to_cf_id")
    if from_cf_id is None or to_cf_id is None:
        messages.error(
            request,
            "Invalid or missing from_cf_id or to_cf_id GET parameter",
        )
        return HttpResponseRedirect(f"/patch/{patchid}/")

    from_cf = get_object_or_404(CommitFest, pk=from_cf_id)
    to_cf = get_object_or_404(CommitFest, pk=to_cf_id)

    patch = get_object_or_404(Patch, pk=patchid)
    try:
        patch.move(from_cf, to_cf, request.user)
    except UserInputError as e:
        messages.error(request, f"Failed to move patch: {e}")
        return HttpResponseRedirect(f"/patch/{patchid}/")

    return HttpResponseRedirect(f"/patch/{patchid}/")


@require_POST
@login_required
@transaction.atomic
def reviewer(request, patchid, status):
    patch = get_object_or_404(Patch, pk=patchid)

    is_reviewer = request.user in patch.reviewers.all()

    if status == "become" and not is_reviewer:
        patch.reviewers.add(request.user)
        patch.set_modified()
        PatchHistory(
            patch=patch,
            by=request.user,
            what="Added %s as reviewer" % request.user.username,
        ).save_and_notify()
    elif status == "remove" and is_reviewer:
        patch.reviewers.remove(request.user)
        patch.set_modified()
        PatchHistory(
            patch=patch,
            by=request.user,
            what="Removed %s from reviewers" % request.user.username,
        ).save_and_notify()
    return HttpResponseRedirect("../../")


@require_POST
@login_required
@transaction.atomic
def remove_all_reviewers(request, patchid):
    patch = get_object_or_404(Patch, pk=patchid)

    if not patch.can_remove_all_reviewers:
        return HttpResponseForbidden(
            "Removing reviewers is only allowed for PGConf.dev patches."
        )

    prevreviewers = list(patch.reviewers.all())
    if not prevreviewers:
        return HttpResponseRedirect(f"/patch/{patchid}/")

    patch.reviewers.clear()
    patch.set_modified()
    patch.save()
    PatchHistory(
        patch=patch,
        by=request.user,
        what="Removed all reviewers",
    ).save_and_notify(prevreviewers=prevreviewers)
    return HttpResponseRedirect(f"/patch/{patchid}/")


@require_POST
@login_required
@transaction.atomic
def committer(request, patchid, status):
    patch = get_object_or_404(Patch, pk=patchid)

    committer = list(Committer.objects.filter(user=request.user, active=True))
    if len(committer) == 0:
        return HttpResponseForbidden("Only committers can do that!")
    committer = committer[0]

    is_committer = committer == patch.committer

    prevcommitter = patch.committer
    if status == "become" and not is_committer:
        patch.committer = committer
        patch.set_modified()
        PatchHistory(
            patch=patch,
            by=request.user,
            what="Added %s as committer" % request.user.username,
        ).save_and_notify(prevcommitter=prevcommitter)
    elif status == "remove" and is_committer:
        patch.committer = None
        patch.set_modified()
        PatchHistory(
            patch=patch,
            by=request.user,
            what="Removed %s from committers" % request.user.username,
        ).save_and_notify(prevcommitter=prevcommitter)
    patch.save()
    return HttpResponseRedirect("../../")


@require_POST
@login_required
@transaction.atomic
def subscribe(request, patchid, sub):
    patch = get_object_or_404(Patch, pk=patchid)

    if sub == "un":
        patch.subscribers.remove(request.user)
        messages.info(request, "You have been unsubscribed from updates on this patch")
    else:
        patch.subscribers.add(request.user)
        messages.info(request, "You have been subscribed to updates on this patch")
    patch.save()
    return HttpResponseRedirect("../")


def send_patch_email(request, patchid):
    patch = get_object_or_404(Patch, pk=patchid)
    cf = patch.current_commitfest()
    return send_email(request, cf.id)


@login_required
@transaction.atomic
def send_email(request, cfid):
    cf = get_object_or_404(CommitFest, pk=cfid)
    if not request.user.is_staff:
        raise Http404("Only CF managers can do that.")

    if request.method == "POST":
        authoridstring = request.POST["authors"]
        revieweridstring = request.POST["reviewers"]
        form = BulkEmailForm(data=request.POST)
        if form.is_valid():
            q = Q()
            if authoridstring:
                q = q | Q(patch_author__in=[int(x) for x in authoridstring.split(",")])
            if revieweridstring:
                q = q | Q(
                    patch_reviewer__in=[int(x) for x in revieweridstring.split(",")]
                )

            recipients = User.objects.filter(q).distinct()

            # We send from our own address instead of the manager's, because
            # many domains have a DMARC policy that causes emails with their
            # address in the From header to be rejected when they're not sent
            # through their own mail servers. Reply-To makes replies still go
            # to the manager.
            uw = UserWrapper(request.user)
            for r in recipients:
                send_simple_mail(
                    settings.NOTIFICATION_FROM,
                    r.email,
                    form.cleaned_data["subject"],
                    form.cleaned_data["body"],
                    request.user.username,
                    sendername="%s %s via PostgreSQL Commitfest"
                    % (request.user.first_name, request.user.last_name),
                    replyto=uw.encoded_email_header,
                )
                messages.add_message(
                    request, messages.INFO, "Sent email to %s" % r.email
                )
            return HttpResponseRedirect("..")
    else:
        authoridstring = request.GET.get("authors", None)
        revieweridstring = request.GET.get("reviewers", None)
        form = BulkEmailForm(
            initial={"authors": authoridstring, "reviewers": revieweridstring}
        )

    if authoridstring:
        authors = list(
            User.objects.filter(
                patch_author__in=[int(x) for x in authoridstring.split(",")]
            ).distinct()
        )
    else:
        authors = []
    if revieweridstring:
        reviewers = list(
            User.objects.filter(
                patch_reviewer__in=[int(x) for x in revieweridstring.split(",")]
            ).distinct()
        )
    else:
        reviewers = []

    if len(authors) == 0 and len(reviewers) == 0:
        messages.add_message(
            request, messages.WARNING, "No recipients specified, cannot send email"
        )
        return HttpResponseRedirect("..")

    messages.add_message(
        request,
        messages.INFO,
        "Email will be sent from %s, with replies going to: %s"
        % (settings.NOTIFICATION_FROM, UserWrapper(request.user).email),
    )

    def _user_and_mail(u):
        return "%s %s (%s)" % (u.first_name, u.last_name, u.email)

    if len(authors):
        messages.add_message(
            request,
            messages.INFO,
            "The email will be sent to the following authors: %s"
            % ", ".join([_user_and_mail(u) for u in authors]),
        )
    if len(reviewers):
        messages.add_message(
            request,
            messages.INFO,
            "The email will be sent to the following reviewers: %s"
            % ", ".join([_user_and_mail(u) for u in reviewers]),
        )

    return render(
        request,
        "base_form.html",
        {
            "cf": cf,
            "form": form,
            "title": "Send email",
            "breadcrumbs": [
                {"title": cf.title, "href": "/%s/" % cf.pk},
            ],
            "savebutton": "Send email",
        },
    )


@transaction.atomic
def cfbot_ingest(message):
    """Ingest a single message status update message receive from cfbot.  It
    should be a Python dictionary, decoded from JSON already."""

    cursor = connection.cursor()

    branch_status = message["branch_status"]
    patch_id = branch_status["submission_id"]
    branch_id = branch_status["branch_id"]

    try:
        patch = Patch.objects.get(pk=patch_id)
    except Patch.DoesNotExist:
        # If the patch doesn't exist, there's nothing to do. This should never
        # happen in production, but on the test system it's possible because
        # not it doesn't contain the newest patches that the CFBot knows about.
        return

    # Every message should have a branch_status, which we will INSERT
    # or UPDATE.  We do this first, because cfbot_task refers to it.
    # Due to the way messages are sent/queued by cfbot it's possible that it
    # sends the messages out-of-order. To handle this we we only update in two
    # cases:
    # 1. The created time of the branch is newer than the one in our database:
    #    This is a newer branch
    # 2. If it's the same branch that we already have, but the modified time is
    #    newer: This is a status update for the current branch that we received
    #    in-order.
    cursor.execute(
        """INSERT INTO commitfest_cfbotbranch (patch_id, branch_id,
                                                branch_name, commit_id,
                                                apply_url, build_url, status,
                                                created, modified,
                                                version, patch_count,
                                                first_additions, first_deletions,
                                                all_additions, all_deletions
                                                )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (patch_id) DO UPDATE
                        SET status = EXCLUDED.status,
                            modified = EXCLUDED.modified,
                            branch_id = EXCLUDED.branch_id,
                            branch_name = EXCLUDED.branch_name,
                            commit_id = EXCLUDED.commit_id,
                            apply_url = EXCLUDED.apply_url,
                            build_url = EXCLUDED.build_url,
                            created = EXCLUDED.created,
                            version = EXCLUDED.version,
                            patch_count = EXCLUDED.patch_count,
                            first_additions = EXCLUDED.first_additions,
                            first_deletions = EXCLUDED.first_deletions,
                            all_additions = EXCLUDED.all_additions,
                            all_deletions = EXCLUDED.all_deletions
                        WHERE commitfest_cfbotbranch.created < EXCLUDED.created
                            OR (commitfest_cfbotbranch.branch_id = EXCLUDED.branch_id
                                AND commitfest_cfbotbranch.modified < EXCLUDED.modified)
                        """,
        (
            patch_id,
            branch_id,
            branch_status["branch_name"],
            branch_status["commit_id"],
            branch_status["apply_url"],
            branch_status["build_url"],
            branch_status["status"],
            branch_status["created"],
            branch_status["modified"],
            branch_status["version"],
            branch_status["patch_count"],
            branch_status["first_additions"],
            branch_status["first_deletions"],
            branch_status["all_additions"],
            branch_status["all_deletions"],
        ),
    )

    # Now we check what we have in our database. If that contains a different
    # branch_id than what we just tried to insert, then apparently this is a
    # status update for an old branch and we don't care about any of the
    # contents of this message.
    branch_in_db = CfbotBranch.objects.get(pk=patch_id)
    if branch_in_db.branch_id != branch_id:
        return

    # Most messages have a task_status.  It might be missing in rare cases, like
    # when cfbot decides that a whole branch has timed out.  We INSERT or
    # UPDATE.
    if "task_status" in message:
        task_status = message["task_status"]
        if task_status["status"] in [x[0] for x in CfbotTask.STATUS_CHOICES]:
            cursor.execute(
                """INSERT INTO commitfest_cfbottask (task_id, task_url, task_name, patch_id, branch_id,
                                                position, status,
                                                created, modified)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (branch_id, position) DO UPDATE
                            SET task_id = EXCLUDED.task_id,
                                task_url = EXCLUDED.task_url,
                                task_name = EXCLUDED.task_name,
                                status = EXCLUDED.status,
                                created = EXCLUDED.created,
                                modified = EXCLUDED.modified
                        WHERE commitfest_cfbottask.modified < EXCLUDED.modified""",
                (
                    task_status["task_id"],
                    task_status["task_url"],
                    task_status["task_name"],
                    patch_id,
                    branch_id,
                    task_status["position"],
                    task_status["status"],
                    task_status["created"],
                    task_status["modified"],
                ),
            )

    # Remove any old tasks that are not related to this branch. These should
    # only be left over when we just updated the branch_id. Knowing if we just
    # updated the branch_id was is not trivial though, because INSERT ON
    # CONFLICT does not allow us to easily return the old value of the row.
    # So instead we always delete all tasks that are not related to this
    # branch. This is fine, because doing so is very cheap in the no-op case
    # because we have an index on patch_id and there's only a handful of tasks
    # per patch.
    cursor.execute(
        "DELETE FROM commitfest_cfbottask WHERE patch_id=%s AND branch_id != %s",
        (patch_id, branch_id),
    )

    # We change the needs_rebase field using a separate UPDATE because this way
    # we can find out what the previous state of the field was (sadly INSERT ON
    # CONFLICT does not allow us to return that). We need to know the previous
    # state so we can skip sending notifications if the needs_rebase status did
    # not change.
    needs_save = False
    # Check if patch has at least one open poc - only open patches can need rebase
    has_open_poc = PatchOnCommitFest.objects.filter(
        patch=patch, status__in=PatchOnCommitFest.OPEN_STATUSES
    ).exists()
    needs_rebase = branch_status["commit_id"] is None and has_open_poc
    if bool(branch_in_db.needs_rebase_since) is not needs_rebase:
        if needs_rebase:
            branch_in_db.needs_rebase_since = datetime.now()
        else:
            branch_in_db.needs_rebase_since = None
        needs_save = True

        if needs_rebase:
            PatchHistory(
                patch=patch, by=None, by_cfbot=True, what="Patch needs rebase"
            ).save_and_notify(authors_only=True)
        else:
            PatchHistory(
                patch=patch,
                by=None,
                by_cfbot=True,
                what="Patch does not need rebase anymore",
            ).save_and_notify(authors_only=True)

    # Similarly, we change the failing_since field using a separate UPDATE
    failing = branch_status["status"] in ("failed", "timeout") or needs_rebase
    finished = branch_status["status"] == "finished"

    if (
        "task_status" in message
        and message["task_status"]["status"]
        in (
            "ABORTED",
            "ERRORED",
            "FAILED",
        )
        and message["task_status"]["task_name"] != "FormattingCheck"
    ):
        failing = True

    if (failing or finished) and bool(branch_in_db.failing_since) is not failing:
        if failing:
            branch_in_db.failing_since = datetime.now()
        else:
            branch_in_db.failing_since = None
        needs_save = True

    if needs_save:
        branch_in_db.save()


@csrf_exempt
def cfbot_notify(request):
    if request.method != "POST":
        return HttpResponseForbidden(b"Invalid method")

    j = json.loads(request.body)
    if not hmac.compare_digest(j["shared_secret"], settings.CFBOT_SECRET):
        return HttpResponseForbidden(b"Invalid API key")

    cfbot_ingest(j)
    return HttpResponse(status=200)


@csrf_exempt
def thread_notify(request):
    if request.method != "POST":
        return HttpResponseForbidden(b"Invalid method")

    j = json.loads(request.body)
    if j["apikey"] != settings.ARCHIVES_APIKEY:
        return HttpResponseForbidden(b"Invalid API key")

    for m in j["messageids"]:
        t = MailThread.objects.get(messageid=m)
        refresh_single_thread(t)

    return HttpResponse(status=200)


@login_required
def cfbot_requeue(request, patchid):
    """Trigger a requeue of a patch in the cfbot."""
    if request.method != "POST":
        return HttpResponseForbidden(b"Invalid method")

    patch = get_object_or_404(Patch, pk=patchid)
    cf = patch.current_commitfest()

    # Make API call to cfbot
    import requests

    payload = {
        "commitfest_id": cf.id,
        "submission_id": patchid,
        "shared_secret": settings.CFBOT_SECRET,
    }

    try:
        response = requests.post(
            f"{settings.CFBOT_API_URL}/requeue-patch", json=payload, timeout=10
        )
        if response.status_code == 200:
            messages.success(request, "Patch requeued successfully")
        else:
            messages.error(request, f"Failed to requeue patch: {response.status_code}")
    except requests.exceptions.RequestException as e:
        messages.error(request, f"Failed to requeue patch: {e}")

    return HttpResponseRedirect(f"/patch/{patchid}/")
