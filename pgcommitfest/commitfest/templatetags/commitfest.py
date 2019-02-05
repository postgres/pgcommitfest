from django.template.defaultfilters import stringfilter
from django import template

from pgcommitfest.commitfest.models import PatchOnCommitFest

register = template.Library()

@register.filter(name='patchstatusstring')
@stringfilter
def patchstatusstring(value):
    i = int(value)
    return [v for k,v in PatchOnCommitFest._STATUS_CHOICES if k==i][0]

@register.filter(name='patchstatuslabel')
@stringfilter
def patchstatuslabel(value):
    i = int(value)
    return [v for k,v in PatchOnCommitFest._STATUS_LABELS if k==i][0]

@register.filter(is_safe=True)
def label_class(value, arg):
    return value.label_tag(attrs={'class': arg})

@register.filter(is_safe=True)
def field_class(value, arg):
    return value.as_widget(attrs={"class": arg})

@register.filter(name='alertmap')
@stringfilter
def alertmap(value):
    if value == 'error':
        return 'alert-danger'
    elif value == 'warning':
        return 'alert-warning'
    elif value == 'success':
        return 'alert-success'
    else:
        return 'alert-info'

@register.filter(name='hidemail')
@stringfilter
def hidemail(value):
    return value.replace('@', ' at ')
