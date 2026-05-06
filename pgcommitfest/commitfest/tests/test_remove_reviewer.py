from datetime import datetime

import pytest

from pgcommitfest.commitfest.models import (
    Patch,
    PatchHistory,
    PatchOnCommitFest,
    PendingNotification,
    Tag,
)
from pgcommitfest.userprofile.models import UserProfile

pytestmark = pytest.mark.django_db


def test_remove_all_reviewers(client, open_cf, alice, bob, charlie):
    UserProfile.objects.create(user=bob, notify_all_reviewer=True)

    pgconfdev_tag = Tag.objects.create(
        name="PGConf.dev", color="#000000", description="PGConf.dev"
    )
    patch = Patch.objects.create(name="Test patch")
    patch.authors.add(alice)
    patch.reviewers.add(bob, charlie)
    patch.tags.add(pgconfdev_tag)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=open_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    client.force_login(alice)
    response = client.get(f"/patch/{patch.id}/reviewer/remove_all/")
    assert response.status_code == 302
    assert list(patch.reviewers.all()) == []
    assert (
        "Removed all reviewers"
        in PatchHistory.objects.filter(patch=patch).latest("date").what
    )
    assert PendingNotification.objects.filter(user=bob).exists()


def test_remove_all_reviewers_forbidden_without_tag(client, open_cf, alice, bob):
    patch = Patch.objects.create(name="Test patch")
    patch.authors.add(alice)
    patch.reviewers.add(bob)
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=open_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )

    client.force_login(alice)
    response = client.get(f"/patch/{patch.id}/reviewer/remove_all/")
    assert response.status_code == 403
    assert bob in patch.reviewers.all()
