from django.contrib import admin
from django.utils.timezone import now
from .models import *

class CommitfestAdmin(admin.ModelAdmin):
    @admin.action(description="Start selected Commitfest")
    def startCommitfest(self,request,queryset):
        for commitfest in queryset:
            if commitfest.status == 2:
                commitfest.status = 3
            commitfest.save()
    @admin.action(description="End selected Commitfest")
    def endCommitfest(self,request,queryset):
        for commitfest in queryset:
            if commitfest.status == 3:
                commitfest.status = 4
                commitfest.enddate = now()
                commitfest.save()
    actions = [startCommitfest, endCommitfest]

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

admin.site.register(Committer, CommitterAdmin)
admin.site.register(CommitFest,CommitfestAdmin)
admin.site.register(Topic)
admin.site.register(Patch, PatchAdmin)
admin.site.register(PatchHistory)
admin.site.register(TargetVersion)
admin.site.register(CfbotBranch)
admin.site.register(CfbotTask)

admin.site.register(MailThread)
admin.site.register(MailThreadAttachment, MailThreadAttachmentAdmin)
