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


class MailThreadAdmin(admin.ModelAdmin):
    list_display = (
        "messageid",
        "subject",
        "firstmessage",
        "latestmsgid",
        "latestmessage",
    )


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


class CfbotBranchAdmin(admin.ModelAdmin):
    # Without this the patch field is rendered as a dropdown, for which every
    # patch in the database gets fetched and rendered as an <option>. That
    # makes the page extremely slow to load. With raw_id_fields it's rendered
    # as a simple text input containing the patch id instead.
    raw_id_fields = ("patch",)


class CfbotTaskAdmin(admin.ModelAdmin):
    # See CfbotBranchAdmin for why raw_id_fields is used here.
    raw_id_fields = ("patch",)


admin.site.register(Committer, CommitterAdmin)
admin.site.register(CommitFest)
admin.site.register(Tag, TagAdmin)
admin.site.register(Topic)
admin.site.register(Patch, PatchAdmin)
admin.site.register(PatchHistory)
admin.site.register(TargetVersion)
admin.site.register(CfbotBranch, CfbotBranchAdmin)
admin.site.register(CfbotTask, CfbotTaskAdmin)

admin.site.register(MailThread, MailThreadAdmin)
admin.site.register(MailThreadAttachment, MailThreadAttachmentAdmin)
