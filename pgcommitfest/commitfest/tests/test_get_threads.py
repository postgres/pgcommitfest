from django.test import RequestFactory

from unittest.mock import patch

from pgcommitfest.commitfest.ajax import getThreads


def _msg(msgid, date, subj):
    return {"msgid": msgid, "date": date, "from": "a@example.com", "subj": subj}


HACKERS = [
    _msg("h1@example.com", "2026-01-03T00:00:00", "hackers thread"),
    _msg("both@example.com", "2026-01-01T00:00:00", "sent to both lists"),
]
BUGS = [
    _msg("b1@example.com", "2026-01-02T00:00:00", "BUG #1: bugs thread"),
    _msg("both@example.com", "2026-01-01T00:00:00", "sent to both lists"),
]


def _fake_archives(suburl, params=None):
    return {
        "/list/pgsql-hackers/latest.json": HACKERS,
        "/list/pgsql-bugs/latest.json": BUGS,
    }[suburl]


def test_get_threads_searches_hackers_and_bugs():
    """The thread search should return threads from pgsql-bugs too."""
    request = RequestFactory().get("/ajax/getThreads/", {"s": "thread", "a": "1"})

    with patch(
        "pgcommitfest.commitfest.ajax._archivesAPI", side_effect=_fake_archives
    ) as api:
        result = getThreads(request)

    # Both lists are searched with the same parameters
    assert [c.args for c in api.call_args_list] == [
        ("/list/pgsql-hackers/latest.json", {"n": 100, "a": 1, "s": "thread"}),
        ("/list/pgsql-bugs/latest.json", {"n": 100, "a": 1, "s": "thread"}),
    ]

    # Results are merged newest first, and the message sent to both lists
    # shows up only once
    assert [m["msgid"] for m in result] == [
        "h1@example.com",
        "b1@example.com",
        "both@example.com",
    ]


def test_get_threads_limits_merged_result():
    """Merging two lists should not return more than one list would."""
    hackers = [
        _msg("h%d@example.com" % i, "2026-01-01T00:%02d:00" % (i % 60), "h")
        for i in range(100)
    ]
    bugs = [
        _msg("b%d@example.com" % i, "2026-01-02T00:%02d:00" % (i % 60), "b")
        for i in range(100)
    ]

    def fake(suburl, params=None):
        return hackers if "pgsql-hackers" in suburl else bugs

    request = RequestFactory().get("/ajax/getThreads/")
    with patch("pgcommitfest.commitfest.ajax._archivesAPI", side_effect=fake):
        result = getThreads(request)

    assert len(result) == 100
    # The bugs messages are all newer, so they are the ones that are kept
    assert all(m["msgid"].startswith("b") for m in result)
