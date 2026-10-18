from django.db import OperationalError

import pytest

from pgcommitfest.commitfest.views import retry_on_serialization_failure


def _pg_error(pgcode):
    # Django re-raises psycopg2 errors with ``from``, so the SQLSTATE is only
    # reachable through ``__cause__.pgcode``, which is what the decorator reads.
    cause = Exception("underlying psycopg2 error")
    cause.pgcode = pgcode
    error = OperationalError("could not serialize access due to concurrent update")
    error.__cause__ = cause
    return error


@pytest.mark.parametrize(
    "pgcode,failures,expected_calls",
    [
        ("40001", 1, 2),  # serialization failure, recovers
        ("40P01", 1, 2),  # deadlock, recovers
        ("40001", 99, 2),  # persistent failure, gives up after one retry
        ("57014", 99, 1),  # query_canceled is not transient, no retry
    ],
)
def test_retry_on_serialization_failure(pgcode, failures, expected_calls):
    calls = []

    @retry_on_serialization_failure
    def view():
        calls.append(1)
        if len(calls) <= failures:
            raise _pg_error(pgcode)
        return "ok"

    if failures >= expected_calls:
        with pytest.raises(OperationalError):
            view()
    else:
        assert view() == "ok"
    assert len(calls) == expected_calls
