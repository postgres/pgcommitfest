from django import forms

from .models import UserExtraEmail, UserProfile


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        exclude = ("user",)

    def __init__(self, user, *args, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.user = user

        mailhelp = 'To add a new address to choose from, update your user profile on <a href="https://www.postgresql.org/account/profile/">postgresql.org</a>.'

        self.fields["selectedemail"].empty_label = self.user.email
        self.fields["selectedemail"].queryset = UserExtraEmail.objects.filter(
            user=self.user
        )
        self.fields["selectedemail"].help_text = mailhelp
        self.fields["notifyemail"].empty_label = self.user.email
        self.fields["notifyemail"].queryset = UserExtraEmail.objects.filter(
            user=self.user
        )
        self.fields["notifyemail"].help_text = mailhelp
