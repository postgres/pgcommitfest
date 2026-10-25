from datetime import datetime

import pytest

from pgcommitfest.commitfest.models import Patch, PatchOnCommitFest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("logged_in", [False, True])
def test_get_does_not_modify_patch(client, open_cf, alice, logged_in):
    patch = Patch.objects.create(name="Test patch")
    poc = PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=open_cf,
        enterdate=datetime.now(),
        status=PatchOnCommitFest.STATUS_REVIEW,
    )
    if logged_in:
        client.force_login(alice)

    response = client.get(f"/patch/{patch.id}/status/author/")
    assert response.status_code == 405
    poc.refresh_from_db()
    assert poc.status == PatchOnCommitFest.STATUS_REVIEW

    response = client.post(f"/patch/{patch.id}/status/author/")
    poc.refresh_from_db()
    assert (poc.status == PatchOnCommitFest.STATUS_AUTHOR) == logged_in
