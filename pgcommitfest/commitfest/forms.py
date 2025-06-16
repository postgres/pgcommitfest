from django import forms
from django.contrib.auth.models import User
from django.forms import ValidationError
from django.forms.widgets import HiddenInput
from django.http import Http404

from .ajax import _archivesAPI
from .models import MailThread, Patch, PatchOnCommitFest, Tag, TargetVersion
from .widgets import ThreadPickWidget


class CommitFestFilterForm(forms.Form):
    selectize_fields = {
        "author": "/lookups/user",
        "reviewer": "/lookups/user",
        "tag": None,
    }

    text = forms.CharField(max_length=50, required=False)
    status = forms.ChoiceField(required=False)
    targetversion = forms.ChoiceField(required=False)
    tag = forms.MultipleChoiceField(required=False, label="Tag (type to search)")
    author = forms.ChoiceField(required=False, label="Author (type to search)")
    reviewer = forms.ChoiceField(required=False, label="Reviewer (type to search)")
    sortkey = forms.IntegerField(required=False)

    def __init__(self, data, *args, **kwargs):
        super(CommitFestFilterForm, self).__init__(data, *args, **kwargs)

        self.fields["sortkey"].widget = forms.HiddenInput()

        c = [(-1, "* All")] + list(PatchOnCommitFest._STATUS_CHOICES)
        self.fields["status"] = forms.ChoiceField(choices=c, required=False)

        userchoices = [(-1, "* All"), (-2, "* None"), (-3, "* Yourself")]

        selected_user_ids = set()
        if data and "author" in data:
            try:
                selected_user_ids.add(int(data["author"]))
            except ValueError:
                pass

        if data and "reviewer" in data:
            try:
                selected_user_ids.add(int(data["reviewer"]))
            except ValueError:
                pass

        if selected_user_ids:
            userchoices.extend(
                (u.id, f"{u.first_name} {u.last_name} ({u.username})")
                for u in User.objects.filter(pk__in=selected_user_ids)
            )

        self.fields["targetversion"] = forms.ChoiceField(
            choices=[("-1", "* All"), ("-2", "* None")]
            + [(v.id, v.version) for v in TargetVersion.objects.all()],
            required=False,
            label="Target version",
        )
        self.fields["author"].choices = userchoices
        self.fields["reviewer"].choices = userchoices
        self.fields["tag"].choices = list(Tag.objects.all().values_list("id", "name"))

        for f in (
            "status",
            "author",
            "reviewer",
        ):
            self.fields[f].widget.attrs = {"class": "input-medium"}


class PatchForm(forms.ModelForm):
    selectize_fields = {
        "authors": "/lookups/user",
        "reviewers": "/lookups/user",
        "tags": None,
    }

    class Meta:
        model = Patch
        exclude = (
            "commitfests",
            "mailthread_set",
            "modified",
            "lastmail",
            "subscribers",
        )

    def __init__(self, *args, **kwargs):
        super(PatchForm, self).__init__(*args, **kwargs)
        self.fields["authors"].help_text = "Enter part of name to see list"
        self.fields["reviewers"].help_text = "Enter part of name to see list"
        self.fields["committer"].label_from_instance = lambda x: "%s %s (%s)" % (
            x.user.first_name,
            x.user.last_name,
            x.user.username,
        )

        self.fields["authors"].widget.attrs["class"] = "add-user-picker"
        self.fields["reviewers"].widget.attrs["class"] = "add-user-picker"

        # Selectize multiple fields -- don't pre-populate everything
        for field, url in list(self.selectize_fields.items()):
            if url is None:
                continue

            # If this is a postback of a selectize field, it may contain ids that are not currently
            # stored in the field. They must still be among the *allowed* values of course, which
            # are handled by the existing queryset on the field.
            if self.instance.pk:
                # If this object isn't created yet, then it by definition has no related
                # objects, so just bypass the collection of values since it will cause
                # errors.
                vals = [o.pk for o in getattr(self.instance, field).all()]
            else:
                vals = []
            if "data" in kwargs and str(field) in kwargs["data"]:
                vals.extend([x for x in kwargs["data"].getlist(field)])
            self.fields[field].widget.attrs["data-selecturl"] = url
            self.fields[field].queryset = self.fields[field].queryset.filter(
                pk__in=set(vals)
            )
            self.fields[field].label_from_instance = (
                lambda u: f"{u.get_full_name()} ({u.username})"
            )

        # Only allow modifying reviewers and committers if the patch is closed.
        if (
            self.instance.id is None
            or self.instance.current_patch_on_commitfest().is_open
        ):
            del self.fields["committer"]
            del self.fields["reviewers"]


class NewPatchForm(PatchForm):
    # Put threadmsgid first
    field_order = ["threadmsgid"]

    threadmsgid = forms.CharField(
        max_length=200,
        required=True,
        label="Specify thread msgid",
        widget=ThreadPickWidget,
    )

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super(NewPatchForm, self).__init__(*args, **kwargs)

        if request:
            self.fields["authors"].queryset = User.objects.filter(pk=request.user.id)
            self.fields["authors"].initial = [request.user.id]

    def clean_threadmsgid(self):
        try:
            _archivesAPI("/message-id.json/%s" % self.cleaned_data["threadmsgid"])
        except Http404:
            raise ValidationError("Message not found in archives")
        except Exception:
            raise ValidationError("Error in API call to validate thread")
        return self.cleaned_data["threadmsgid"]


def _fetch_thread_choices(patch):
    for mt in patch.mailthread_set.order_by("-latestmessage"):
        ti = sorted(
            _archivesAPI("/message-id.json/%s" % mt.messageid),
            key=lambda x: x["date"],
            reverse=True,
        )
        yield [
            mt.subject,
            [
                (
                    "%s,%s" % (mt.messageid, t["msgid"]),
                    "From %s at %s" % (t["from"], t["date"]),
                )
                for t in ti
            ],
        ]


review_state_choices = (
    (0, "Tested"),
    (1, "Passed"),
)


def reviewfield(label):
    return forms.MultipleChoiceField(
        choices=review_state_choices,
        label=label,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )


class CommentForm(forms.Form):
    responseto = forms.ChoiceField(choices=[], required=True, label="In response to")

    # Specific checkbox fields for reviews
    review_installcheck = reviewfield("make installcheck-world")
    review_implements = reviewfield("Implements feature")
    review_spec = reviewfield("Spec compliant")
    review_doc = reviewfield("Documentation")

    message = forms.CharField(required=True, widget=forms.Textarea)
    newstatus = forms.ChoiceField(
        choices=PatchOnCommitFest.OPEN_STATUS_CHOICES(), label="New status"
    )

    def __init__(self, patch, poc, is_review, *args, **kwargs):
        super(CommentForm, self).__init__(*args, **kwargs)
        self.is_review = is_review

        self.fields["responseto"].choices = _fetch_thread_choices(patch)
        self.fields["newstatus"].initial = poc.status
        if not is_review:
            del self.fields["review_installcheck"]
            del self.fields["review_implements"]
            del self.fields["review_spec"]
            del self.fields["review_doc"]

    def clean_responseto(self):
        try:
            (threadid, respid) = self.cleaned_data["responseto"].split(",")
            self.thread = MailThread.objects.get(messageid=threadid)
            self.respid = respid
        except MailThread.DoesNotExist:
            raise ValidationError("Selected thread appears to no longer exist")
        except Exception:
            raise ValidationError("Invalid message selected")
        return self.cleaned_data["responseto"]

    def clean(self):
        if self.is_review:
            for fn, f in self.fields.items():
                if fn.startswith("review_") and fn in self.cleaned_data:
                    if (
                        "1" in self.cleaned_data[fn]
                        and "0" not in self.cleaned_data[fn]
                    ):
                        self.errors[fn] = (
                            ("Cannot pass a test without performing it!"),
                        )
        return self.cleaned_data


class BulkEmailForm(forms.Form):
    reviewers = forms.CharField(required=False, widget=HiddenInput())
    authors = forms.CharField(required=False, widget=HiddenInput())
    subject = forms.CharField(required=True)
    body = forms.CharField(required=True, widget=forms.Textarea)
    confirm = forms.BooleanField(required=True, label="Check to confirm sending")

    def __init__(self, *args, **kwargs):
        super(BulkEmailForm, self).__init__(*args, **kwargs)
