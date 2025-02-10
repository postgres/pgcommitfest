from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import UserProfile
from .forms import UserProfileForm


@login_required
@transaction.atomic
def userprofile(request):
    (profile, created) = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = UserProfileForm(request.user, request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.add_message(request, messages.INFO, "User profile saved.")
            return HttpResponseRedirect(".")
    else:
        form = UserProfileForm(request.user, instance=profile)

    return render(
        request,
        "userprofileform.html",
        {
            "form": form,
        },
    )
