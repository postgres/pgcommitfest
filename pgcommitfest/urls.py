from django.urls import re_path
from django.contrib import admin

import pgcommitfest.commitfest.views as views
import pgcommitfest.commitfest.reports as reports
import pgcommitfest.commitfest.ajax as ajax
import pgcommitfest.commitfest.lookups as lookups
import pgcommitfest.auth
import pgcommitfest.userprofile.views

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
admin.autodiscover()


urlpatterns = [
    re_path(r'^$', views.home),
    re_path(r'^activity(?P<rss>\.rss)?/', views.activity),
    re_path(r'^(\d+)/$', views.commitfest),
    re_path(r'^(open|inprogress|current)/(.*)$', views.redir),
    re_path(r'^(?P<cfid>\d+)/activity(?P<rss>\.rss)?/$', views.activity),
    re_path(r'^(\d+)/(\d+)/$', views.patch_legacy_redirect),
    re_path(r'^patch/(\d+)/$', views.patch),
    re_path(r'^patch/(\d+)/edit/$', views.patchform),
    re_path(r'^(\d+)/new/$', views.newpatch),
    re_path(r'^patch/(\d+)/status/(review|author|committer)/$', views.status),
    re_path(r'^patch/(\d+)/close/(reject|withdrawn|feedback|committed|next)/$', views.close),
    re_path(r'^patch/(\d+)/reviewer/(become|remove)/$', views.reviewer),
    re_path(r'^patch/(\d+)/committer/(become|remove)/$', views.committer),
    re_path(r'^patch/(\d+)/(un)?subscribe/$', views.subscribe),
    re_path(r'^patch/(\d+)/(comment|review)/', views.comment),
    re_path(r'^(\d+)/send_email/$', views.send_email),
    re_path(r'^patch/(\d+)/send_email/$', views.send_patch_email),
    re_path(r'^(\d+)/reports/authorstats/$', reports.authorstats),
    re_path(r'^search/$', views.global_search),
    re_path(r'^ajax/(\w+)/$', ajax.main),
    re_path(r'^lookups/user/$', lookups.userlookup),
    re_path(r'^thread_notify/$', views.thread_notify),
    re_path(r'^cfbot_notify/$', views.cfbot_notify),

    # Legacy email POST route. This can be safely removed in a few days from
    # the first time this is deployed. It's only puprose is not breaking
    # submissions from a previous page lood, during the deploy of the new
    # /patch/(\d+) routes. It would be a shame if someone lost their well
    # written email because of this.
    re_path(r'^\d+/(\d+)/send_email/$', views.send_patch_email),

    # Auth system integration
    re_path(r'^(?:account/)?login/?$', pgcommitfest.auth.login),
    re_path(r'^(?:account/)?logout/?$', pgcommitfest.auth.logout),
    re_path(r'^auth_receive/$', pgcommitfest.auth.auth_receive),
    re_path(r'^auth_api/$', pgcommitfest.auth.auth_api),

    # Account management
    re_path(r'^account/profile/$', pgcommitfest.userprofile.views.userprofile),

    # Examples:
    # re_path(r'^$', 'pgpgcommitfest.commitfest.views.home', name='home),
    # re_path(r'^pgcommitfest/', include('pgcommitfest.foo.urls)),

    # Uncomment the admin/doc line below to enable admin documentation:
    # re_path(r'^admin/doc/', include('django.contrib.admindocs.urls)),

    # Uncomment the next line to enable the admin:
    re_path(r'^admin/', admin.site.urls),
]
