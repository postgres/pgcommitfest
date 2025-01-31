from django.contrib import admin

from .models import *


class CommitterAdmin(admin.ModelAdmin):
    list_display = ('user', 'active')


class PatchOnCommitFestInline(admin.TabularInline):
    model = PatchOnCommitFest
    extra = 1


class PatchAdmin(admin.ModelAdmin):
    inlines = (PatchOnCommitFestInline,)
    list_display = ('name', )


class MailThreadAttachmentAdmin(admin.ModelAdmin):
    list_display = ('date', 'author', 'messageid', 'mailthread',)


admin.site.register(Committer, CommitterAdmin)
admin.site.register(CommitFest)
admin.site.register(Topic)
admin.site.register(Patch, PatchAdmin)
admin.site.register(PatchHistory)
admin.site.register(TargetVersion)
admin.site.register(CfbotBranch)
admin.site.register(CfbotTask)

admin.site.register(MailThread)
admin.site.register(MailThreadAttachment, MailThreadAttachmentAdmin)
