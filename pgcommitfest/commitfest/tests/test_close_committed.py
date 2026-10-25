from datetime import datetime

import pytest

from pgcommitfest.commitfest.models import Committer, Patch, PatchOnCommitFest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "status",
    [PatchOnCommitFest.STATUS_REVIEW, PatchOnCommitFest.STATUS_RETURNED],
)
def test_commit_moves_patch_to_in_progress_cf(
    client, open_cf, in_progress_cf, alice, status
):
    Committer.objects.create(user=alice)
    patch = Patch.objects.create(name="Test patch")
    poc = PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=open_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )
    poc.set_status(status)

    client.force_login(alice)
    response = client.post(f"/patch/{patch.id}/close/committed/?c={alice.username}")
    assert response.status_code == 302

    old_poc = PatchOnCommitFest.objects.get(patch=patch, commitfest=open_cf)
    assert old_poc.status == PatchOnCommitFest.STATUS_MOVED
    new_poc = PatchOnCommitFest.objects.get(patch=patch, commitfest=in_progress_cf)
    assert new_poc.status == PatchOnCommitFest.STATUS_COMMITTED
    patch.refresh_from_db()
    assert patch.committer.user == alice
