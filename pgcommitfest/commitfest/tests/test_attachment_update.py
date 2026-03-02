from datetime import datetime

import pytest

from pgcommitfest.commitfest.ajax import parse_and_add_attachments
from pgcommitfest.commitfest.models import MailThread, MailThreadAttachment

pytestmark = pytest.mark.django_db


def _make_thread():
    return MailThread.objects.create(
        messageid="test@example.com",
        subject="Test",
        firstmessage=datetime(2024, 1, 1),
        firstauthor="a@example.com",
        latestmessage=datetime(2024, 1, 1),
        latestauthor="a@example.com",
        latestsubject="Test",
        latestmsgid="test@example.com",
    )


def test_attachment_id_updated_on_reindex():
    """Regression test: attachmentid must be updated when the archive re-indexes."""
    thread = _make_thread()

    old_api_response = [
        {
            "msgid": "msg1@example.com",
            "date": datetime(2024, 1, 1),
            "from": "author@example.com",
            "subj": "Test",
            "atts": [{"id": 37937, "name": "patch_v1.diff"}],
        },
    ]
    parse_and_add_attachments(old_api_response, thread)

    att = MailThreadAttachment.objects.get(
        mailthread=thread, messageid="msg1@example.com"
    )
    assert att.attachmentid == 37937
    assert att.filename == "patch_v1.diff"

    # Simulate archive re-indexing: same message, new attachment ID
    new_api_response = [
        {
            "msgid": "msg1@example.com",
            "date": datetime(2024, 1, 1),
            "from": "author@example.com",
            "subj": "Test",
            "atts": [{"id": 90866, "name": "patch_v1.diff"}],
        },
    ]
    parse_and_add_attachments(new_api_response, thread)

    att.refresh_from_db()
    assert att.attachmentid == 90866, (
        f"Expected attachmentid to be updated to 90866, got {att.attachmentid}"
    )


def test_attachment_filename_updated_on_reindex():
    """Filename should also be updated if it changes."""
    thread = _make_thread()

    api_response = [
        {
            "msgid": "msg2@example.com",
            "date": datetime(2024, 2, 1),
            "from": "author@example.com",
            "subj": "Test",
            "atts": [{"id": 100, "name": "old_name.patch"}],
        },
    ]
    parse_and_add_attachments(api_response, thread)

    att = MailThreadAttachment.objects.get(
        mailthread=thread, messageid="msg2@example.com"
    )
    assert att.filename == "old_name.patch"

    api_response[0]["atts"][0]["name"] = "new_name.patch"
    api_response[0]["atts"][0]["id"] = 200
    parse_and_add_attachments(api_response, thread)

    att.refresh_from_db()
    assert att.filename == "new_name.patch"
    assert att.attachmentid == 200


def test_attachment_created_when_new():
    """New attachments should still be created correctly."""
    thread = _make_thread()

    api_response = [
        {
            "msgid": "new@example.com",
            "date": datetime(2024, 3, 1),
            "from": "author@example.com",
            "subj": "Test",
            "atts": [{"id": 555, "name": "feature.patch"}],
        },
    ]
    parse_and_add_attachments(api_response, thread)

    att = MailThreadAttachment.objects.get(
        mailthread=thread, messageid="new@example.com"
    )
    assert att.attachmentid == 555
    assert att.filename == "feature.patch"


def test_messages_without_attachments_ignored():
    """Messages with no attachments should not create any records."""
    thread = _make_thread()

    api_response = [
        {
            "msgid": "noatt@example.com",
            "date": datetime(2024, 4, 1),
            "from": "author@example.com",
            "subj": "Test",
            "atts": [],
        },
    ]
    parse_and_add_attachments(api_response, thread)

    assert not MailThreadAttachment.objects.filter(
        mailthread=thread, messageid="noatt@example.com"
    ).exists()
