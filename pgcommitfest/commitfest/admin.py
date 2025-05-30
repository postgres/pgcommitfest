from django.contrib import admin
from django.forms import widgets

from .models import (
    CfbotBranch,
    CfbotTask,
    ColorField,
    CommitFest,
    Committer,
    MailThread,
    MailThreadAttachment,
    Patch,
    PatchHistory,
    PatchOnCommitFest,
    Tag,
    TargetVersion,
    Topic,
)


class CommitterAdmin(admin.ModelAdmin):
    list_display = ("user", "active")


class PatchOnCommitFestInline(admin.TabularInline):
    model = PatchOnCommitFest
    extra = 1


class PatchAdmin(admin.ModelAdmin):
    inlines = (PatchOnCommitFestInline,)
    list_display = ("name",)


class MailThreadAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "author",
        "messageid",
        "mailthread",
    )


class ColorInput(widgets.Input):
    """
    A color picker widget.
    TODO: this will be natively available in Django 5.2.
    """

    input_type = "color"


class TagAdmin(admin.ModelAdmin):
    formfield_overrides = {
        ColorField: {"widget": ColorInput},
    }


admin.site.register(Committer, CommitterAdmin)
admin.site.register(CommitFest)
admin.site.register(Tag, TagAdmin)
admin.site.register(Topic)
admin.site.register(Patch, PatchAdmin)
admin.site.register(PatchHistory)
admin.site.register(TargetVersion)
admin.site.register(CfbotBranch)
admin.site.register(CfbotTask)

admin.site.register(MailThread)
admin.site.register(MailThreadAttachment, MailThreadAttachmentAdmin)
