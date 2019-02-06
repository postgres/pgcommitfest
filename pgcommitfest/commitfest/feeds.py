from django.contrib.syndication.views import Feed


class ActivityFeed(Feed):
    title = description = 'Commitfest Activity Log'
    link = 'https://commitfest.postgresql.org/'

    def __init__(self, activity, cf, *args, **kwargs):
        super(ActivityFeed, self).__init__(*args, **kwargs)
        self.activity = activity
        if cf:
            self.cfid = cf.id
            self.title = self.description = 'PostgreSQL Commitfest {0} Activity Log'.format(cf.name)
        else:
            self.cfid = None

    def items(self):
        return self.activity

    def item_title(self, item):
        if self.cfid:
            return item['name']
        else:
            return '{cfname}: {name}'.format(**item)

    def item_description(self, item):
        if self.cfid:
            return "<div>Patch: {name}</div><div>User: {by}</div>\n<div>{what}</div>".format(**item)
        else:
            return "<div>Commitfest: {cfname}</div><div>Patch: {name}</div><div>User: {by}</div><div>{what}</div>".format(**item)

    def item_link(self, item):
        if self.cfid:
            return 'https://commitfest.postgresql.org/{cfid}/{patchid}/'.format(cfid=self.cfid, **item)
        else:
            return 'https://commitfest.postgresql.org/{cfid}/{patchid}/'.format(**item)

    def item_pubdate(self, item):
        return item['date']
