from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.http import Http404, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, connection
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from django.conf import settings

from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
import json
import hmac
import urllib

from pgcommitfest.mailqueue.util import send_mail, send_simple_mail
from pgcommitfest.userprofile.util import UserWrapper

from .models import CommitFest, Patch, PatchOnCommitFest, PatchHistory, Committer, CfbotBranch, CfbotTask
from .models import MailThread
from .forms import PatchForm, NewPatchForm, CommentForm, CommitFestFilterForm
from .forms import BulkEmailForm
from .ajax import doAttachThread, refresh_single_thread, _archivesAPI
from .feeds import ActivityFeed


def home(request):
    commitfests = list(CommitFest.objects.all())
    opencf = next((c for c in commitfests if c.status == CommitFest.STATUS_OPEN), None)
    inprogresscf = next((c for c in commitfests if c.status == CommitFest.STATUS_INPROGRESS), None)

    return render(request, 'home.html', {
        'commitfests': commitfests,
        'opencf': opencf,
        'inprogresscf': inprogresscf,
        'title': 'Commitfests',
        'header_activity': 'Activity log',
        'header_activity_link': '/activity/',
    })


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
        where = 'WHERE EXISTS (SELECT 1 FROM commitfest_patchoncommitfest poc2 WHERE poc2.patch_id=p.id AND poc2.commitfest_id={0})'.format(cf.id)
    else:
        cf = None
        where = ''

    sql = "SELECT ph.date, auth_user.username AS by, ph.what, p.id AS patchid, p.name, (SELECT max(commitfest_id) FROM commitfest_patchoncommitfest poc WHERE poc.patch_id=p.id) AS cfid FROM commitfest_patchhistory ph INNER JOIN commitfest_patch p ON ph.patch_id=p.id INNER JOIN auth_user on auth_user.id=ph.by_id {0} ORDER BY ph.date DESC LIMIT {1}".format(where, num)

    curs = connection.cursor()
    curs.execute(sql)
    activity = [dict(zip([c[0] for c in curs.description], r)) for r in curs.fetchall()]

    if rss:
        # Return RSS feed with these objects
        return ActivityFeed(activity, cf)(request)
    else:
        # Return regular webpage
        return render(request, 'activity.html', {
            'commitfest': cf,
            'activity': activity,
            'title': cf and 'Commitfest activity' or 'Global Commitfest activity',
            'rss_alternate': cf and '/{0}/activity.rss/'.format(cf.id) or '/activity.rss/',
            'rss_alternate_title': 'PostgreSQL Commitfest Activity Log',
            'breadcrumbs': cf and [{'title': cf.title, 'href': '/%s/' % cf.pk}, ] or None,
        })


def redir(request, what, end):
    if what == 'open':
        cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_OPEN))
    elif what == 'inprogress':
        cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_INPROGRESS))
    elif what == 'current':
        cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_INPROGRESS))
        if len(cfs) == 0:
            cfs = list(CommitFest.objects.filter(status=CommitFest.STATUS_OPEN))
    else:
        raise Http404()

    if len(cfs) == 0:
        messages.warning(request, "No {0} commitfests exist, redirecting to startpage.".format(what))
        return HttpResponseRedirect("/")
    if len(cfs) != 1:
        messages.warning(request, "More than one {0} commitfest exists, redirecting to startpage instead.".format(what))
        return HttpResponseRedirect("/")

    query_string = request.GET.urlencode()
    if query_string:
        query_string = '?' + query_string
    return HttpResponseRedirect(f"/{cfs[0].id}/{end}{query_string}")


def commitfest(request, cfid):
    # Find ourselves
    cf = get_object_or_404(CommitFest, pk=cfid)

    # Build a dynamic filter based on the filtering options entered
    whereclauses = []
    whereparams = {}
    if request.GET.get('status', '-1') != '-1':
        try:
            whereparams['status'] = int(request.GET['status'])
            whereclauses.append("poc.status=%(status)s")
        except ValueError:
            # int() failed -- so just ignore this filter
            pass

    if request.GET.get('targetversion', '-1') != '-1':
        if request.GET['targetversion'] == '-2':
            whereclauses.append("targetversion_id IS NULL")
        else:
            try:
                whereparams['verid'] = int(request.GET['targetversion'])
                whereclauses.append("targetversion_id=%(verid)s")
            except ValueError:
                # int() failed, ignore
                pass

    if request.GET.get('author', '-1') != '-1':
        if request.GET['author'] == '-2':
            whereclauses.append("NOT EXISTS (SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id)")
        elif request.GET['author'] == '-3':
            # Checking for "yourself" requires the user to be logged in!
            if not request.user.is_authenticated:
                return HttpResponseRedirect('%s?next=%s' % (settings.LOGIN_URL, request.path))
            whereclauses.append("EXISTS (SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id AND cpa.user_id=%(self)s)")
            whereparams['self'] = request.user.id
        else:
            try:
                whereparams['author'] = int(request.GET['author'])
                whereclauses.append("EXISTS (SELECT 1 FROM commitfest_patch_authors cpa WHERE cpa.patch_id=p.id AND cpa.user_id=%(author)s)")
            except ValueError:
                # int() failed -- so just ignore this filter
                pass

    if request.GET.get('reviewer', '-1') != '-1':
        if request.GET['reviewer'] == '-2':
            whereclauses.append("NOT EXISTS (SELECT 1 FROM commitfest_patch_reviewers cpr WHERE cpr.patch_id=p.id)")
        elif request.GET['reviewer'] == '-3':
            # Checking for "yourself" requires the user to be logged in!
            if not request.user.is_authenticated:
                return HttpResponseRedirect('%s?next=%s' % (settings.LOGIN_URL, request.path))
            whereclauses.append("EXISTS (SELECT 1 FROM commitfest_patch_reviewers cpr WHERE cpr.patch_id=p.id AND cpr.user_id=%(self)s)")
            whereparams['self'] = request.user.id
        else:
            try:
                whereparams['reviewer'] = int(request.GET['reviewer'])
                whereclauses.append("EXISTS (SELECT 1 FROM commitfest_patch_reviewers cpr WHERE cpr.patch_id=p.id AND cpr.user_id=%(reviewer)s)")
            except ValueError:
                # int() failed -- so just ignore this filter
                pass

    if request.GET.get('text', '') != '':
        whereclauses.append("p.name ILIKE '%%' || %(txt)s || '%%'")
        whereparams['txt'] = request.GET['text']

    has_filter = len(whereclauses) > 0

    # Figure out custom ordering
    if request.GET.get('sortkey', '') != '':
        try:
            sortkey = int(request.GET['sortkey'])
        except ValueError:
            sortkey = 0

        if sortkey == 1:
            orderby_str = 'modified, created'
        elif sortkey == 2:
            orderby_str = 'lastmail, created'
        elif sortkey == 3:
            orderby_str = 'num_cfs DESC, modified, created'
        elif sortkey == 4:
            orderby_str = 'p.id'
        elif sortkey == 5:
            orderby_str = 'p.name, created'
        else:
            orderby_str = 'p.id'
            sortkey = 0
    else:
        orderby_str = 'topic, created'
        sortkey = 0

    if not has_filter and sortkey == 0 and request.GET:
        # Redirect to get rid of the ugly url
        return HttpResponseRedirect('/%s/' % cf.id)

    if whereclauses:
        where_str = 'AND ({0})'.format(' AND '.join(whereclauses))
    else:
        where_str = ''
    params = {
        'cid': cf.id,
        'openstatuses': PatchOnCommitFest.OPEN_STATUSES,
    }
    params.update(whereparams)

    # Let's not overload the poor django ORM
    curs = connection.cursor()
    curs.execute("""SELECT p.id, p.name, poc.status, v.version AS targetversion, p.created, p.modified, p.lastmail, committer.username AS committer, t.topic,
(poc.status=ANY(%(openstatuses)s)) AS is_open,
(SELECT string_agg(first_name || ' ' || last_name || ' (' || username || ')', ', ') FROM auth_user INNER JOIN commitfest_patch_authors cpa ON cpa.user_id=auth_user.id WHERE cpa.patch_id=p.id) AS author_names,
(SELECT string_agg(first_name || ' ' || last_name || ' (' || username || ')', ', ') FROM auth_user INNER JOIN commitfest_patch_reviewers cpr ON cpr.user_id=auth_user.id WHERE cpr.patch_id=p.id) AS reviewer_names,
(SELECT count(1) FROM commitfest_patchoncommitfest pcf WHERE pcf.patch_id=p.id) AS num_cfs,
(
    SELECT row_to_json(t) as cfbot_results
    from (
        SELECT
            count(*) FILTER (WHERE task.status = 'COMPLETED') as completed,
            count(*) FILTER (WHERE task.status in ('CREATED', 'SCHEDULED', 'EXECUTING')) running,
            count(*) FILTER (WHERE task.status in ('ABORTED', 'ERRORED', 'FAILED')) failed,
            count(*) total,
            string_agg(task.task_name, ', ') FILTER (WHERE task.status in ('ABORTED', 'ERRORED', 'FAILED')) as failed_task_names,
            branch.commit_id IS NULL as needs_rebase,
            branch.apply_url
        FROM commitfest_cfbotbranch branch
        LEFT JOIN commitfest_cfbottask task ON task.branch_id = branch.branch_id
        WHERE branch.patch_id=p.id
        GROUP BY branch.patch_id
    ) t
)
FROM commitfest_patch p
INNER JOIN commitfest_patchoncommitfest poc ON poc.patch_id=p.id
INNER JOIN commitfest_topic t ON t.id=p.topic_id
LEFT JOIN auth_user committer ON committer.id=p.committer_id
LEFT JOIN commitfest_targetversion v ON p.targetversion_id=v.id
WHERE poc.commitfest_id=%(cid)s {0}
GROUP BY p.id, poc.id, committer.id, t.id, v.version
ORDER BY is_open DESC, {1}""".format(where_str, orderby_str), params)
    patches = [dict(zip([col[0] for col in curs.description], row)) for row in curs.fetchall()]

    # Generate patch status summary.
    curs = connection.cursor()
    curs.execute("SELECT ps.status, ps.statusstring, count(*) FROM commitfest_patchoncommitfest poc INNER JOIN commitfest_patchstatus ps ON ps.status=poc.status WHERE commitfest_id=%(id)s GROUP BY ps.status ORDER BY ps.sortkey", {
        'id': cf.id,
    })
    statussummary = curs.fetchall()
    statussummary.append([-1, 'Total', sum((r[2] for r in statussummary))])

    # Generates a fairly expensive query, which we shouldn't do unless
    # the user is logged in. XXX: Figure out how to avoid doing that..
    form = CommitFestFilterForm(cf, request.GET)

    return render(request, 'commitfest.html', {
        'cf': cf,
        'form': form,
        'patches': patches,
        'statussummary': statussummary,
        'has_filter': has_filter,
        'title': cf.title,
        'grouping': sortkey == 0,
        'sortkey': sortkey,
        'openpatchids': [p['id'] for p in patches if p['is_open']],
        'header_activity': 'Activity log',
        'header_activity_link': 'activity/',
    })


def patches_by_messageid(messageid):
    # First try to find the messageid in our database
    patches = Patch.objects.select_related().filter(mailthread__messageid=messageid).order_by('created', ).all()
    if patches:
        return patches

    urlsafe_messageid = urllib.parse.quote(messageid)

    # If it's not there, try to find it in the archives
    try:
        thread = _archivesAPI(f'/message-id.json/{urlsafe_messageid}')
    except Http404:
        return []

    if len(thread) == 0:
        return []

    first_email = min(thread, key=lambda x: x['date'])

    return Patch.objects.select_related().filter(mailthread__messageid=first_email['msgid']).order_by('created',).all()


def global_search(request):
    if 'searchterm' not in request.GET:
        return HttpResponseRedirect('/')
    searchterm = request.GET['searchterm'].strip()
    patches = []

    if '@' in searchterm:
        # This is probably a messageid, so let's try to look up patches related
        # to it. Let's first remove any < and > around it though.
        cleaned_id = searchterm.removeprefix('<').removesuffix('>')
        patches = patches_by_messageid(cleaned_id)

    if not patches:
        patches = Patch.objects.select_related().filter(name__icontains=searchterm).order_by('created',).all()

    if len(patches) == 1:
        patch = patches[0]
        return HttpResponseRedirect(f'/patch/{patch.id}/')

    return render(request, 'patchsearch.html', {
        'patches': patches,
        'title': 'Patch search results',
    })


def patch_legacy_redirect(request, cfid, patchid):
    # Previously we would include the commitfest id in the URL. This is no
    # longer the case.
    return HttpResponseRedirect(f'/patch/{patchid}/')


def patch(request, patchid):
    patch = get_object_or_404(Patch.objects.select_related(), pk=patchid)

    patch_commitfests = PatchOnCommitFest.objects.select_related('commitfest').filter(patch=patch).order_by('-commitfest__startdate').all()
    cf = patch_commitfests[0].commitfest

    committers = Committer.objects.filter(active=True).order_by('user__last_name', 'user__first_name')

    cfbot_branch = getattr(patch, 'cfbot_branch', None)
    cfbot_tasks = patch.cfbot_tasks.order_by('position') if cfbot_branch else []

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

    return render(request, 'patch.html', {
        'cf': cf,
        'patch': patch,
        'patch_commitfests': patch_commitfests,
        'cfbot_branch': cfbot_branch,
        'cfbot_tasks': cfbot_tasks,
        'is_committer': is_committer,
        'is_this_committer': is_this_committer,
        'is_reviewer': is_reviewer,
        'is_subscribed': is_subscribed,
        'committers': committers,
        'attachnow': 'attachthreadnow' in request.GET,
        'title': patch.name,
        'breadcrumbs': [{'title': cf.title, 'href': '/%s/' % cf.pk}, ],
    })


@login_required
@transaction.atomic
def patchform(request, patchid):
    patch = get_object_or_404(Patch, pk=patchid)
    cf = patch.current_commitfest()

    prevreviewers = list(patch.reviewers.all())
    prevauthors = list(patch.authors.all())
    prevcommitter = patch.committer

    if request.method == 'POST':
        form = PatchForm(data=request.POST, instance=patch)
        if form.is_valid():
            # Some fields need to be set when creating a new one
            r = form.save(commit=False)
            # Fill out any locked fields here

            form.save_m2m()

            # Track all changes
            for field, values in r.diff.items():
                PatchHistory(patch=patch, by=request.user, what='Changed %s to %s' % (field, values[1])).save_and_notify(prevcommitter=prevcommitter, prevreviewers=prevreviewers, prevauthors=prevauthors)
            r.set_modified()
            r.save()
            return HttpResponseRedirect('../../%s/' % r.pk)
        # Else fall through and render the page again
    else:
        form = PatchForm(instance=patch)

    return render(request, 'base_form.html', {
        'cf': cf,
        'form': form,
        'patch': patch,
        'title': 'Edit patch',
        'selectize_multiple_fields': form.selectize_multiple_fields.items(),
        'breadcrumbs': [{'title': cf.title, 'href': '/%s/' % cf.pk},
                        {'title': 'View patch', 'href': '/%s/%s/' % (cf.pk, patch.pk)}],
    })


@login_required
@transaction.atomic
def newpatch(request, cfid):
    cf = get_object_or_404(CommitFest, pk=cfid)
    if not cf.status == CommitFest.STATUS_OPEN and not request.user.is_staff:
        raise Http404("This commitfest is not open!")

    if request.method == 'POST':
        form = NewPatchForm(data=request.POST)
        if form.is_valid():
            patch = Patch(name=form.cleaned_data['name'],
                          topic=form.cleaned_data['topic'])
            patch.set_modified()
            patch.save()
            poc = PatchOnCommitFest(patch=patch, commitfest=cf, enterdate=datetime.now())
            poc.save()
            PatchHistory(patch=patch, by=request.user, what='Created patch record').save()
            # Now add the thread
            try:
                doAttachThread(cf, patch, form.cleaned_data['threadmsgid'], request.user)
                return HttpResponseRedirect("/%s/%s/edit/" % (cf.id, patch.id))
            except Http404:
                # Thread not found!
                # This is a horrible breakage of API layers
                form._errors['threadmsgid'] = form.error_class(('Selected thread did not exist in the archives',))
            except Exception:
                form._errors['threadmsgid'] = form.error_class(('An error occurred looking up the thread in the archives.',))
            # In this case, we have created a patch - delete it. This causes a agp in id's, but it should
            # not happen very often. If we successfully attached to it, we will have already returned.
            patch.delete()
    else:
        form = NewPatchForm()

    return render(request, 'base_form.html', {
        'form': form,
        'title': 'New patch',
        'breadcrumbs': [{'title': cf.title, 'href': '/%s/' % cf.pk}, ],
        'savebutton': 'Create patch',
        'threadbrowse': True,
    })


def _review_status_string(reviewstatus):
    if '0' in reviewstatus:
        if '1' in reviewstatus:
            return "tested, passed"
        else:
            return "tested, failed"
    else:
        return "not tested"


@login_required
@transaction.atomic
def comment(request, patchid, what):
    patch = get_object_or_404(Patch, pk=patchid)
    cf = patch.current_commitfest()
    poc = get_object_or_404(PatchOnCommitFest, patch=patch, commitfest=cf)
    is_review = (what == 'review')

    if request.method == 'POST':
        try:
            form = CommentForm(patch, poc, is_review, data=request.POST)
        except Exception as e:
            messages.add_message(request, messages.ERROR, "Failed to build list of response options from the archives: %s" % e)
            return HttpResponseRedirect('/%s/%s/' % (cf.id, patch.id))

        if form.is_valid():
            if is_review:
                txt = "The following review has been posted through the commitfest application:\n%s\n\n%s" % (
                    "\n".join(["%-25s %s" % (f.label + ':', _review_status_string(form.cleaned_data[fn])) for (fn, f) in form.fields.items() if fn.startswith('review_')]),
                    form.cleaned_data['message']
                )
            else:
                txt = form.cleaned_data['message']

            if int(form.cleaned_data['newstatus']) != poc.status:
                poc.status = int(form.cleaned_data['newstatus'])
                poc.save()
                PatchHistory(patch=poc.patch, by=request.user, what='New status: %s' % poc.statusstring).save_and_notify()
                txt += "\n\nThe new status of this patch is: %s\n" % poc.statusstring

            msg = MIMEText(txt, _charset='utf-8')

            if form.thread.subject.startswith('Re:'):
                msg['Subject'] = form.thread.subject
            else:
                msg['Subject'] = 'Re: %s' % form.thread.subject

            msg['To'] = settings.HACKERS_EMAIL
            msg['From'] = UserWrapper(request.user).encoded_email_header

            # CC the authors of a patch, if there are any
            authors = list(patch.authors.all())
            if len(authors):
                msg['Cc'] = ", ".join([UserWrapper(a).encoded_email_header for a in authors])

            msg['Date'] = formatdate(localtime=True)
            msg['User-Agent'] = 'pgcommitfest'
            msg['X-cfsender'] = request.user.username
            msg['In-Reply-To'] = '<%s>' % form.respid
            # We just add the "top" messageid and the one we're responding to.
            # This along with in-reply-to should indicate clearly enough where
            # in the thread the message belongs.
            msg['References'] = '<%s> <%s>' % (form.thread.messageid, form.respid)
            msg['Message-ID'] = make_msgid('pgcf')

            uw = UserWrapper(request.user)
            msgstring = msg.as_string()
            send_mail(uw.email, settings.HACKERS_EMAIL, msgstring)
            for a in authors:
                # Actually send a copy directly to the author. Just setting the Cc field doesn't
                # make it deliver the email...
                send_mail(uw.email, UserWrapper(a).email, msgstring)

            PatchHistory(patch=patch, by=request.user, what='Posted %s with messageid %s' % (what, msg['Message-ID'])).save()

            messages.add_message(request, messages.INFO, "Your email has been queued for %s, and will be sent within a few minutes." % (settings.HACKERS_EMAIL))

            return HttpResponseRedirect('/%s/%s/' % (cf.id, patch.id))
    else:
        try:
            form = CommentForm(patch, poc, is_review)
        except Exception as e:
            messages.add_message(request, messages.ERROR, "Failed to build list of response options from the archives: %s" % e)
            return HttpResponseRedirect('/%s/%s/' % (cf.id, patch.id))

    return render(request, 'base_form.html', {
        'cf': cf,
        'form': form,
        'patch': patch,
        'extraformclass': 'patchcommentform',
        'breadcrumbs': [{'title': cf.title, 'href': '/%s/' % cf.pk},
                        {'title': 'View patch', 'href': '/%s/%s/' % (cf.pk, patch.pk)}],
        'title': "Add %s" % what,
        'note': '<b>Note!</b> This form will generate an email to the public mailinglist <i>%s</i>, with sender set to <i>%s</i>!<br/>Please ensure that the email settings for your domain (<a href="https://en.wikipedia.org/wiki/DomainKeys_Identified_Mail" target="_blank">DKIM</a>, <a href="https://en.wikipedia.org/wiki/SPF" target="_blank">SPF</a>) allow emails from external sources.' % (settings.HACKERS_EMAIL, UserWrapper(request.user).email),
        'savebutton': 'Send %s' % what,
    })


@login_required
@transaction.atomic
def status(request, patchid, status):
    patch = get_object_or_404(Patch.objects.select_related(), pk=patchid)
    cf = patch.current_commitfest()
    poc = get_object_or_404(PatchOnCommitFest.objects.select_related(), commitfest__id=cf.id, patch__id=patchid)

    if status == 'review':
        newstatus = PatchOnCommitFest.STATUS_REVIEW
    elif status == 'author':
        newstatus = PatchOnCommitFest.STATUS_AUTHOR
    elif status == 'committer':
        newstatus = PatchOnCommitFest.STATUS_COMMITTER
    else:
        raise Exception("Can't happen")

    if newstatus != poc.status:
        # Only save it if something actually changed
        poc.status = newstatus
        poc.patch.set_modified()
        poc.patch.save()
        poc.save()

        PatchHistory(patch=poc.patch, by=request.user, what='New status: %s' % poc.statusstring).save_and_notify()

    return HttpResponseRedirect('/patch/%s/' % (poc.patch.id))


@login_required
@transaction.atomic
def close(request, patchid, status):
    patch = get_object_or_404(Patch.objects.select_related(), pk=patchid)
    cf = patch.current_commitfest()

    try:
        request_cfid = int(request.GET.get('cfid', ''))
    except ValueError:
        # int() failed, ignore
        request_cfid = None

    if request_cfid is not None and request_cfid != cf.id:
        # The cfid parameter is only added to the /next/ link. That's the only
        # close operation where two people pressing the button at the same time
        # can have unintended effects.
        messages.error(request, "The patch was moved to a new commitfest by someone else. Please double check if you still want to retry this operation.")
        return HttpResponseRedirect('/%s/%s/' % (cf.id, patch.id))

    poc = get_object_or_404(PatchOnCommitFest.objects.select_related(), commitfest__id=cf.id, patch__id=patchid)

    poc.leavedate = datetime.now()

    # We know the status can't be one of the ones below, since we
    # have checked that we're not closed yet. Therefor, we don't
    # need to check if the individual status has changed.
    if status == 'reject':
        poc.status = PatchOnCommitFest.STATUS_REJECTED
    elif status == 'withdrawn':
        poc.status = PatchOnCommitFest.STATUS_WITHDRAWN
    elif status == 'feedback':
        poc.status = PatchOnCommitFest.STATUS_RETURNED
    elif status == 'next':
        # Only some patch statuses can actually be moved.
        if poc.status in (PatchOnCommitFest.STATUS_COMMITTED,
                          PatchOnCommitFest.STATUS_NEXT,
                          PatchOnCommitFest.STATUS_RETURNED,
                          PatchOnCommitFest.STATUS_REJECTED):
            # Can't be moved!
            messages.error(request, "A patch in status {0} cannot be moved to next commitfest.".format(poc.statusstring))
            return HttpResponseRedirect('/%s/%s/' % (poc.commitfest.id, poc.patch.id))
        elif poc.status in (PatchOnCommitFest.STATUS_REVIEW,
                            PatchOnCommitFest.STATUS_AUTHOR,
                            PatchOnCommitFest.STATUS_COMMITTER):
            # This one can be moved
            pass
        else:
            messages.error(request, "Invalid existing patch status")

        oldstatus = poc.status

        poc.status = PatchOnCommitFest.STATUS_NEXT
        # Figure out the commitfest to actually put it on
        newcf = CommitFest.objects.filter(status=CommitFest.STATUS_OPEN)
        if len(newcf) == 0:
            # Ok, there is no open CF at all. Let's see if there is a
            # future one.
            newcf = CommitFest.objects.filter(status=CommitFest.STATUS_FUTURE)
            if len(newcf) == 0:
                messages.error(request, "No open and no future commitfest exists!")
                return HttpResponseRedirect('/%s/%s/' % (poc.commitfest.id, poc.patch.id))
            elif len(newcf) != 1:
                messages.error(request, "No open and multiple future commitfests exist!")
                return HttpResponseRedirect('/%s/%s/' % (poc.commitfest.id, poc.patch.id))
        elif len(newcf) != 1:
            messages.error(request, "Multiple open commitfests exists!")
            return HttpResponseRedirect('/%s/%s/' % (poc.commitfest.id, poc.patch.id))
        elif newcf[0] == poc.commitfest:
            # The current open CF is the same one that we are already on.
            # In this case, try to see if there is a future CF we can
            # move it to.
            newcf = CommitFest.objects.filter(status=CommitFest.STATUS_FUTURE)
            if len(newcf) == 0:
                messages.error(request, "Cannot move patch to the same commitfest, and no future commitfests exist!")
                return HttpResponseRedirect('/%s/%s/' % (poc.commitfest.id, poc.patch.id))
            elif len(newcf) != 1:
                messages.error(request, "Cannot move patch to the same commitfest, and multiple future commitfests exist!")
                return HttpResponseRedirect('/%s/%s/' % (poc.commitfest.id, poc.patch.id))
        # Create a mapping to the new commitfest that we are bouncing
        # this patch to.
        newpoc = PatchOnCommitFest(patch=poc.patch,
                                   commitfest=newcf[0],
                                   status=oldstatus,
                                   enterdate=datetime.now())
        newpoc.save()
    elif status == 'committed':
        committer = get_object_or_404(Committer, user__username=request.GET['c'])
        if committer != poc.patch.committer:
            # Committer changed!
            prevcommitter = poc.patch.committer
            poc.patch.committer = committer
            PatchHistory(patch=poc.patch, by=request.user, what='Changed committer to %s' % committer).save_and_notify(prevcommitter=prevcommitter)
        poc.status = PatchOnCommitFest.STATUS_COMMITTED
    else:
        raise Exception("Can't happen")

    poc.patch.set_modified()
    poc.patch.save()
    poc.save()

    PatchHistory(patch=poc.patch, by=request.user, what='Closed in commitfest %s with status: %s' % (poc.commitfest, poc.statusstring)).save_and_notify()

    return HttpResponseRedirect('/%s/%s/' % (poc.commitfest.id, poc.patch.id))


@login_required
@transaction.atomic
def reviewer(request, patchid, status):
    patch = get_object_or_404(Patch, pk=patchid)

    is_reviewer = request.user in patch.reviewers.all()

    if status == 'become' and not is_reviewer:
        patch.reviewers.add(request.user)
        patch.set_modified()
        PatchHistory(patch=patch, by=request.user, what='Added %s as reviewer' % request.user.username).save_and_notify()
    elif status == 'remove' and is_reviewer:
        patch.reviewers.remove(request.user)
        patch.set_modified()
        PatchHistory(patch=patch, by=request.user, what='Removed %s from reviewers' % request.user.username).save_and_notify()
    return HttpResponseRedirect('../../')


@login_required
@transaction.atomic
def committer(request, cfid, patchid, status):
    patch = get_object_or_404(Patch, pk=patchid)

    committer = list(Committer.objects.filter(user=request.user, active=True))
    if len(committer) == 0:
        return HttpResponseForbidden('Only committers can do that!')
    committer = committer[0]

    is_committer = committer == patch.committer

    prevcommitter = patch.committer
    if status == 'become' and not is_committer:
        patch.committer = committer
        patch.set_modified()
        PatchHistory(patch=patch, by=request.user, what='Added %s as committer' % request.user.username).save_and_notify(prevcommitter=prevcommitter)
    elif status == 'remove' and is_committer:
        patch.committer = None
        patch.set_modified()
        PatchHistory(patch=patch, by=request.user, what='Removed %s from committers' % request.user.username).save_and_notify(prevcommitter=prevcommitter)
    patch.save()
    return HttpResponseRedirect('../../')


@login_required
@transaction.atomic
def subscribe(request, patchid, sub):
    patch = get_object_or_404(Patch, pk=patchid)

    if sub == 'un':
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

    if request.method == 'POST':
        authoridstring = request.POST['authors']
        revieweridstring = request.POST['reviewers']
        form = BulkEmailForm(data=request.POST)
        if form.is_valid():
            q = Q()
            if authoridstring:
                q = q | Q(patch_author__in=[int(x) for x in authoridstring.split(',')])
            if revieweridstring:
                q = q | Q(patch_reviewer__in=[int(x) for x in revieweridstring.split(',')])

            recipients = User.objects.filter(q).distinct()

            for r in recipients:
                send_simple_mail(UserWrapper(request.user).email, r.email, form.cleaned_data['subject'], form.cleaned_data['body'], request.user.username)
                messages.add_message(request, messages.INFO, "Sent email to %s" % r.email)
            return HttpResponseRedirect('..')
    else:
        authoridstring = request.GET.get('authors', None)
        revieweridstring = request.GET.get('reviewers', None)
        form = BulkEmailForm(initial={'authors': authoridstring, 'reviewers': revieweridstring})

    if authoridstring:
        authors = list(User.objects.filter(patch_author__in=[int(x) for x in authoridstring.split(',')]).distinct())
    else:
        authors = []
    if revieweridstring:
        reviewers = list(User.objects.filter(patch_reviewer__in=[int(x) for x in revieweridstring.split(',')]).distinct())
    else:
        reviewers = []

    if len(authors) == 0 and len(reviewers) == 0:
        messages.add_message(request, messages.WARNING, "No recipients specified, cannot send email")
        return HttpResponseRedirect('..')

    messages.add_message(request, messages.INFO, "Email will be sent from: %s" % UserWrapper(request.user).email)

    def _user_and_mail(u):
        return "%s %s (%s)" % (u.first_name, u.last_name, u.email)

    if len(authors):
        messages.add_message(request, messages.INFO, "The email will be sent to the following authors: %s" % ", ".join([_user_and_mail(u) for u in authors]))
    if len(reviewers):
        messages.add_message(request, messages.INFO, "The email will be sent to the following reviewers: %s" % ", ".join([_user_and_mail(u) for u in reviewers]))

    return render(request, 'base_form.html', {
        'cf': cf,
        'form': form,
        'title': 'Send email',
        'breadcrumbs': [{'title': cf.title, 'href': '/%s/' % cf.pk}, ],
        'savebutton': 'Send email',
    })


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
    cursor.execute("""INSERT INTO commitfest_cfbotbranch (patch_id, branch_id,
                                                branch_name, commit_id,
                                                apply_url, status,
                                                created, modified)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (patch_id) DO UPDATE
                        SET status = EXCLUDED.status,
                            modified = EXCLUDED.modified,
                            branch_id = EXCLUDED.branch_id,
                            branch_name = EXCLUDED.branch_name,
                            commit_id = EXCLUDED.commit_id,
                            apply_url = EXCLUDED.apply_url,
                            created = EXCLUDED.created
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
                       branch_status["status"],
                       branch_status["created"],
                       branch_status["modified"])
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
        cursor.execute("""INSERT INTO commitfest_cfbottask (task_id, task_name, patch_id, branch_id,
                                               position, status,
                                               created, modified)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (task_id) DO UPDATE
                         SET status = EXCLUDED.status,
                             modified = EXCLUDED.modified
                       WHERE commitfest_cfbottask.modified < EXCLUDED.modified""",
                       (
                           task_status["task_id"],
                           task_status["task_name"],
                           patch_id,
                           branch_id,
                           task_status["position"],
                           task_status["status"],
                           task_status["created"],
                           task_status["modified"])
                       )

    # Remove any old tasks that are not related to this branch. These should
    # only be left over when we just updated the branch_id. Knowing if we just
    # updated the branch_id was is not trivial though, because INSERT ON
    # CONFLICT does not allow us to easily return the old value of the row.
    # So instead we always delete all tasks that are not related to this
    # branch. This is fine, because doing so is very cheap in the no-op case
    # because we have an index on patch_id and there's only a handful of tasks
    # per patch.
    cursor.execute("DELETE FROM commitfest_cfbottask WHERE patch_id=%s AND branch_id != %s", (patch_id, branch_id))

    # We change the needs_rebase field using a separate UPDATE because this way
    # we can find out what the previous state of the field was (sadly INSERT ON
    # CONFLICT does not allow us to return that). We need to know the previous
    # state so we can skip sending notifications if the needs_rebase status did
    # not change.
    needs_rebase = branch_status['commit_id'] is None
    if bool(branch_in_db.needs_rebase_since) is not needs_rebase:
        if needs_rebase:
            branch_in_db.needs_rebase_since = datetime.now()
        else:
            branch_in_db.needs_rebase_since = None
        branch_in_db.save()

        if needs_rebase:
            PatchHistory(patch=patch, by=None, by_cfbot=True, what='Patch needs rebase').save_and_notify(authors_only=True)
        else:
            PatchHistory(patch=patch, by=None, by_cfbot=True, what='Patch does not need rebase anymore').save_and_notify(authors_only=True)


@csrf_exempt
def cfbot_notify(request):
    if request.method != 'POST':
        return HttpResponseForbidden("Invalid method")

    j = json.loads(request.body)
    if not hmac.compare_digest(j['shared_secret'], settings.CFBOT_SECRET):
        return HttpResponseForbidden("Invalid API key")

    cfbot_ingest(j)
    return HttpResponse(status=200)


@csrf_exempt
def thread_notify(request):
    if request.method != 'POST':
        return HttpResponseForbidden("Invalid method")

    j = json.loads(request.body)
    if j['apikey'] != settings.ARCHIVES_APIKEY:
        return HttpResponseForbidden("Invalid API key")

    for m in j['messageids']:
        try:
            t = MailThread.objects.get(messageid=m)
            refresh_single_thread(t)
        except Exception as e:
            # Just ignore it, we'll check again later
            pass

    return HttpResponse(status=200)
