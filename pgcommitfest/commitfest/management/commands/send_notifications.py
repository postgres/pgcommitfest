from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings


from pgcommitfest.commitfest.models import PendingNotification
from pgcommitfest.userprofile.models import UserProfile
from pgcommitfest.mailqueue.util import send_template_mail


class Command(BaseCommand):
    help = "Send queued notifications"

    def handle(self, *args, **options):
        with transaction.atomic():
            # Django doesn't do proper group by in the ORM, so we have to
            # build our own.
            matches = {}
            for n in PendingNotification.objects.all().order_by('user', 'history__patch__id', 'history__id'):
                if n.user.id not in matches:
                    matches[n.user.id] = {'user': n.user, 'patches': {}}
                if n.history.patch.id not in matches[n.user.id]['patches']:
                    matches[n.user.id]['patches'][n.history.patch.id] = {'patch': n.history.patch, 'entries': []}
                matches[n.user.id]['patches'][n.history.patch.id]['entries'].append(n.history)
                n.delete()

            # Ok, now let's build emails from this
            for v in matches.values():
                user = v['user']
                email = user.email
                try:
                    if user.userprofile and user.userprofile.notifyemail:
                        email = user.userprofile.notifyemail.email
                except UserProfile.DoesNotExist:
                    pass

                send_template_mail(settings.NOTIFICATION_FROM,
                                   None,
                                   email,
                                   "PostgreSQL commitfest updates",
                                   'mail/patch_notify.txt',
                                   {
                                       'user': user,
                                       'patches': v['patches'],
                                   },
                                   )
