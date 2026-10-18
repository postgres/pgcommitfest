from django.db import connection

from datetime import datetime
from unittest.mock import patch

import pytest

from pgcommitfest.commitfest.models import MailThread, Patch

pytestmark = pytest.mark.django_db


def _fail_with_database_error(*args, **kwargs):
    # A real failing query, not just a raised exception, so that PostgreSQL
    # aborts the transaction and any further query in it would fail too.
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1/0")


@pytest.mark.parametrize(
    "failure",
    [RuntimeError("Simulated failure"), _fail_with_database_error],
    ids=["python-error", "database-error"],
)
def test_newpatch_does_not_leave_orphan_thread(
    client, alice, open_cf, in_progress_cf, recent_closed_cf, failure
):
    client.force_login(alice)

    message = {
        "msgid": "test-thread@example.com",
        "date": datetime(2025, 1, 10, 12),
        "from": "author@example.com",
        "subj": "[PATCH] Test",
        "atts": [],
    }

    with (
        patch(
            "pgcommitfest.commitfest.forms._archivesAPI",
            return_value=[message],
        ),
        patch(
            "pgcommitfest.commitfest.ajax._archivesAPI",
            return_value=[message],
        ),
        patch(
            "pgcommitfest.commitfest.ajax.parse_and_add_attachments",
            side_effect=failure,
        ) as failure_mock,
    ):
        response = client.post(
            f"/{open_cf.pk}/new/",
            {
                "name": "Transaction test",
                "threadmsgid": "test-thread@example.com",
                "no_tags_apply": "on",
                "authors": [str(alice.pk)],
            },
        )

    failure_mock.assert_called_once()
    assert response.status_code == 200
    assert not Patch.objects.filter(name="Transaction test").exists()
    assert not MailThread.objects.filter(messageid="test-thread@example.com").exists()


def test_newpatch_creates_patch_and_attaches_thread(
    client, alice, open_cf, in_progress_cf, recent_closed_cf
):
    client.force_login(alice)

    message = {
        "msgid": "success-thread@example.com",
        "date": datetime(2025, 1, 10, 12),
        "from": "author@example.com",
        "subj": "[PATCH] Success",
        "atts": [],
    }

    with (
        patch(
            "pgcommitfest.commitfest.forms._archivesAPI",
            return_value=[message],
        ),
        patch(
            "pgcommitfest.commitfest.ajax._archivesAPI",
            return_value=[message],
        ),
    ):
        response = client.post(
            f"/{open_cf.pk}/new/",
            {
                "name": "Successful transaction test",
                "threadmsgid": "success-thread@example.com",
                "no_tags_apply": "on",
                "authors": [str(alice.pk)],
            },
        )

    created_patch = Patch.objects.get(name="Successful transaction test")
    thread = MailThread.objects.get(messageid="success-thread@example.com")

    assert response.status_code == 302
    assert response["Location"] == f"/patch/{created_patch.pk}/"
    assert thread.patches.filter(pk=created_patch.pk).exists()
