from email.utils import formataddr
from email.header import Header

from .models import UserProfile, UserExtraEmail


class UserWrapper(object):
    def __init__(self, user):
        self.user = user

    @property
    def email(self):
        try:
            up = UserProfile.objects.get(user=self.user)
            if up.selectedemail:
                return up.selectedemail.email
            else:
                return self.user.email
        except UserProfile.DoesNotExist:
            return self.user.email

    @property
    def encoded_email_header(self):
        return formataddr(
            (
                str(
                    Header(
                        "%s %s" % (self.user.first_name, self.user.last_name), "utf-8"
                    )
                ),
                self.email,
            )
        )


def handle_user_data(sender, **kwargs):
    user = kwargs.pop("user")
    userdata = kwargs.pop("userdata")

    secondary = userdata.get("secondaryemails", [])

    # Remove any email attached to this user that are not upstream. Since the foreign keys
    # are set to SET_NULL, they will all revert to being the users default in this case.
    UserExtraEmail.objects.filter(user=user).exclude(email__in=secondary).delete()

    # Then add back any of the ones that aren't there
    current = set([e.email for e in UserExtraEmail.objects.filter(user=user)])
    for e in set(secondary).difference(current):
        UserExtraEmail(user=user, email=e).save()
