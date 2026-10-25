from django.test import RequestFactory

from unittest.mock import patch

from pgcommitfest.commitfest.ajax import getThreads


def _msg(msgid, date):
    return {"msgid": msgid, "date": date, "from": "a@example.com", "subj": msgid}


def test_get_threads_searches_hackers_and_bugs():
    hackers = [
        _msg(f"h{i}", f"2026-01-01T{i // 60:02d}:{i % 60:02d}:00") for i in range(100)
    ]
    # b1 is newer than everything on hackers, h99 was sent to both lists
    bugs = [_msg("b1", "2026-01-02T00:00:00"), hackers[99]]

    def fake(suburl, params=None):
        return {
            "/list/pgsql-hackers/latest.json": hackers,
            "/list/pgsql-bugs/latest.json": bugs,
        }[suburl]

    request = RequestFactory().get("/ajax/getThreads/", {"s": "x", "a": "1"})
    with patch("pgcommitfest.commitfest.ajax._archivesAPI", side_effect=fake) as api:
        result = getThreads(request)

    assert [c.args for c in api.call_args_list] == [
        ("/list/pgsql-hackers/latest.json", {"n": 100, "a": 1, "s": "x"}),
        ("/list/pgsql-bugs/latest.json", {"n": 100, "a": 1, "s": "x"}),
    ]
    # Merged newest first, h99 deduplicated, and capped at 100 so the oldest
    # message (h0) is dropped.
    assert [m["msgid"] for m in result] == ["b1"] + [f"h{i}" for i in range(99, 0, -1)]
