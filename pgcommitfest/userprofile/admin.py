from django.contrib import admin
from django.db.models import Count, Q

from .models import UserProfile


class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "notify_all_author",
        "notify_all_reviewer",
        "notify_all_committer",
        "show_relative_timestamps",
    )
    list_filter = (
        "notify_all_author",
        "notify_all_reviewer",
        "notify_all_committer",
        "show_relative_timestamps",
    )
    search_fields = ("user__username", "user__first_name", "user__last_name")

    def changelist_view(self, request, extra_context=None):
        stats = UserProfile.objects.aggregate(
            total=Count("id"),
            author_on=Count("id", filter=Q(notify_all_author=True)),
            author_off=Count("id", filter=Q(notify_all_author=False)),
            reviewer_on=Count("id", filter=Q(notify_all_reviewer=True)),
            reviewer_off=Count("id", filter=Q(notify_all_reviewer=False)),
            committer_on=Count("id", filter=Q(notify_all_committer=True)),
            committer_off=Count("id", filter=Q(notify_all_committer=False)),
            timestamps_on=Count("id", filter=Q(show_relative_timestamps=True)),
            timestamps_off=Count("id", filter=Q(show_relative_timestamps=False)),
        )
        extra_context = extra_context or {}
        extra_context["notification_stats"] = stats
        return super().changelist_view(request, extra_context=extra_context)


admin.site.register(UserProfile, UserProfileAdmin)
