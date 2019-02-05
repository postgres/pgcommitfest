from django import forms
from django.contrib.auth.models import User

from models import UserProfile, UserExtraEmail

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        exclude = ('user', )

    def __init__(self, user, *args, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.user = user

        self.fields['selectedemail'].empty_label=self.user.email
        self.fields['selectedemail'].queryset=UserExtraEmail.objects.filter(user=self.user, confirmed=True)
        self.fields['notifyemail'].empty_label=self.user.email
        self.fields['notifyemail'].queryset=UserExtraEmail.objects.filter(user=self.user, confirmed=True)

class MailForm(forms.Form):
    email = forms.EmailField()
    email2 = forms.EmailField(label="Repeat email")

    def clean_email(self):
        email = self.cleaned_data['email']

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use by another account")

        return email

    def clean_email2(self):
        # If the primary email checker had an exception, the data will be gone
        # from the cleaned_data structure
        if not self.cleaned_data.has_key('email'):
            return self.cleaned_data['email2']
        email1 = self.cleaned_data['email']
        email2 = self.cleaned_data['email2']

        if email1 != email2:
            raise forms.ValidationError("Email addresses don't match")

        return email2
