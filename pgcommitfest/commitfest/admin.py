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
    """

    input_type = "color"
    template_name = "color_input.html"


class TagAdmin(admin.ModelAdmin):
    # Customize the Tag form with a color picker and soft validation.
    change_form_template = "change_tag_form.html"
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
