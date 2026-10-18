from django.db import connection

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from pgcommitfest.commitfest.models import MailThread, Patch

pytestmark = pytest.mark.django_db

MSGID = "test-thread@example.com"


def _fail_with_database_error(*args, **kwargs):
    # A real failing query, not just a raised exception, so that PostgreSQL
    # aborts the transaction and any further query in it would fail too.
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1/0")


@pytest.mark.parametrize("fail", [False, True], ids=["success", "database-error"])
def test_newpatch_thread_attach(
    client, alice, open_cf, in_progress_cf, recent_closed_cf, fail
):
    client.force_login(alice)
    message = {
        "msgid": MSGID,
        "date": datetime(2025, 1, 10, 12, tzinfo=timezone.utc),
        "from": "author@example.com",
        "subj": "[PATCH] Test",
        "atts": [],
    }

    with (
        patch("pgcommitfest.commitfest.forms._archivesAPI", return_value=[message]),
        patch("pgcommitfest.commitfest.ajax._archivesAPI", return_value=[message]),
        patch(
            "pgcommitfest.commitfest.ajax.parse_and_add_attachments",
            side_effect=_fail_with_database_error if fail else None,
        ) as attachments_mock,
    ):
        response = client.post(
            f"/{open_cf.pk}/new/",
            {
                "name": "Transaction test",
                "threadmsgid": MSGID,
                "no_tags_apply": "on",
                "authors": [str(alice.pk)],
            },
        )

    attachments_mock.assert_called_once()
    if fail:
        # The form is re-rendered with an error and nothing is left behind
        assert response.status_code == 200
        assert not Patch.objects.filter(name="Transaction test").exists()
        assert not MailThread.objects.filter(messageid=MSGID).exists()
    else:
        created_patch = Patch.objects.get(name="Transaction test")
        assert response.status_code == 302
        assert response["Location"] == f"/patch/{created_patch.pk}/"
        assert (
            MailThread.objects.get(messageid=MSGID)
            .patches.filter(pk=created_patch.pk)
            .exists()
        )
