from django import template
from django.template.defaultfilters import stringfilter

from uuid import uuid4

from pgcommitfest.commitfest.models import PatchOnCommitFest

register = template.Library()


@register.filter(name="patchstatusstring")
@stringfilter
def patchstatusstring(value):
    i = int(value)
    return [v for k, v in PatchOnCommitFest._STATUS_CHOICES if k == i][0]


@register.filter(name="patchstatuslabel")
@stringfilter
def patchstatuslabel(value):
    i = int(value)
    return [v for k, v in PatchOnCommitFest._STATUS_LABELS if k == i][0]


@register.filter(is_safe=True)
def label_class(value, arg):
    return value.label_tag(attrs={"class": arg})


@register.filter(is_safe=True)
def field_class(value, arg):
    return value.as_widget(attrs={"class": arg})


@register.filter(name="alertmap")
@stringfilter
def alertmap(value):
    if value == "error":
        return "alert-danger"
    elif value == "warning":
        return "alert-warning"
    elif value == "success":
        return "alert-success"
    else:
        return "alert-info"


# Generate a GET parameter that's unique per startup of the python process to
# bust the cache of the client, so that it pulls in possibly updated JS/CSS
# files.
STATIC_FILE_PARAM = f"v={uuid4()}"


# This GET parameter should be added to every one of our static files.
@register.simple_tag
def static_file_param():
    return STATIC_FILE_PARAM


@register.filter(name="hidemail")
@stringfilter
def hidemail(value):
    return value.replace("@", " at ")
