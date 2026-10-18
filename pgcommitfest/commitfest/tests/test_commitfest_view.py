from datetime import datetime

import pytest

from pgcommitfest.commitfest.models import Patch, PatchOnCommitFest, PatchStatus

# The commitfest view runs SET TRANSACTION ISOLATION LEVEL as its first
# statement, which fails inside the transaction a regular django_db test wraps
# everything in.
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("draft", [False, True])
def test_closed_patches_hidden_in_draft(client, commitfests, draft):
    cf = commitfests["draft" if draft else "open"]
    for name, status, leavedate in [
        ("Open patch", PatchOnCommitFest.STATUS_REVIEW, None),
        ("Committed patch", PatchOnCommitFest.STATUS_COMMITTED, datetime.now()),
    ]:
        # The transactional test flushes the migration-seeded status table,
        # which the status summary joins against.
        PatchStatus.objects.get_or_create(
            status=status, defaults={"statusstring": name}
        )
        PatchOnCommitFest.objects.create(
            patch=Patch.objects.create(name=name),
            commitfest=cf,
            enterdate=datetime.now(),
            leavedate=leavedate,
            status=status,
        )

    content = client.get(f"/{cf.id}/").content.decode()

    assert "Open patch" in content
    assert ("Committed patch" in content) is not draft
    assert ("Closed patches" in content) is not draft
    committed_summary = f'href="?status={PatchOnCommitFest.STATUS_COMMITTED}"'
    assert (committed_summary in content) is not draft
