from django.conf.urls import patterns, include, url
from django.contrib import admin

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'pgcommitfest.commitfest.views.home'),
    url(r'^activity(?P<rss>\.rss)?/', 'pgcommitfest.commitfest.views.activity'),
    url(r'^(\d+)/$', 'pgcommitfest.commitfest.views.commitfest'),
    url(r'^(open|inprogress)/$', 'pgcommitfest.commitfest.views.redir'),
    url(r'^(?P<cfid>\d+)/activity(?P<rss>\.rss)?/$', 'pgcommitfest.commitfest.views.activity'),
    url(r'^(\d+)/(\d+)/$', 'pgcommitfest.commitfest.views.patch'),
    url(r'^(\d+)/(\d+)/edit/$', 'pgcommitfest.commitfest.views.patchform'),
    url(r'^(\d+)/new/$', 'pgcommitfest.commitfest.views.newpatch'),
    url(r'^(\d+)/(\d+)/status/(review|author|committer)/$', 'pgcommitfest.commitfest.views.status'),
    url(r'^(\d+)/(\d+)/close/(reject|feedback|committed|next)/$', 'pgcommitfest.commitfest.views.close'),
    url(r'^(\d+)/(\d+)/reviewer/(become|remove)/$', 'pgcommitfest.commitfest.views.reviewer'),
    url(r'^(\d+)/(\d+)/committer/(become|remove)/$', 'pgcommitfest.commitfest.views.committer'),
    url(r'^(\d+)/(\d+)/(un)?subscribe/$', 'pgcommitfest.commitfest.views.subscribe'),
    url(r'^(\d+)/(\d+)/(comment|review)/', 'pgcommitfest.commitfest.views.comment'),
    url(r'^(\d+)/send_email/$', 'pgcommitfest.commitfest.views.send_email'),
    url(r'^(\d+)/\d+/send_email/$', 'pgcommitfest.commitfest.views.send_email'),
    url(r'^(\d+)/reports/authorstats/$', 'pgcommitfest.commitfest.reports.authorstats'),
    url(r'^search/$', 'pgcommitfest.commitfest.views.global_search'),
    url(r'^ajax/(\w+)/$', 'pgcommitfest.commitfest.ajax.main'),

    url(r'^selectable/', include('selectable.urls')),

    # Auth system integration
    (r'^(?:account/)?login/?$', 'pgcommitfest.auth.login'),
    (r'^(?:account/)?logout/?$', 'pgcommitfest.auth.logout'),
    (r'^auth_receive/$', 'pgcommitfest.auth.auth_receive'),

    # Account management
    (r'^account/profile/$', 'pgcommitfest.userprofile.views.userprofile'),
    (r'^account/profile/delmail/$', 'pgcommitfest.userprofile.views.deletemail'),
    (r'^account/profile/confirm/([0-9a-f]+)/$', 'pgcommitfest.userprofile.views.confirmemail'),

    # Examples:
    # url(r'^$', 'pgpgcommitfest.commitfest.views.home', name='home'),
    # url(r'^pgcommitfest/', include('pgcommitfest.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)
