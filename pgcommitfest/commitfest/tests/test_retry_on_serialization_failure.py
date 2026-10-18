from django.db import OperationalError

import pytest

from pgcommitfest.commitfest.views import retry_on_serialization_failure


def _pg_error(pgcode):
    """Build an OperationalError that looks like one Django raised from psycopg2.

    Django re-raises the psycopg2 error with ``from`` set, so the SQLSTATE is
    reachable through ``__cause__.pgcode`` -- which is exactly what the decorator
    inspects.
    """
    cause = Exception("underlying psycopg2 error")
    cause.pgcode = pgcode
    error = OperationalError("could not serialize access due to concurrent update")
    error.__cause__ = cause
    return error


def test_retries_serialization_failure_then_succeeds():
    calls = []

    @retry_on_serialization_failure
    def view():
        calls.append(1)
        if len(calls) < 3:
            raise _pg_error("40001")
        return "ok"

    assert view() == "ok"
    # Failed twice with 40001, succeeded on the third attempt.
    assert len(calls) == 3


def test_gives_up_after_persistent_serialization_failures():
    calls = []

    @retry_on_serialization_failure
    def view():
        calls.append(1)
        raise _pg_error("40001")

    with pytest.raises(OperationalError):
        view()
    # Initial attempt plus retries, bounded so we never loop forever.
    assert len(calls) == 5


def test_deadlock_is_also_retried():
    calls = []

    @retry_on_serialization_failure
    def view():
        calls.append(1)
        if len(calls) < 2:
            raise _pg_error("40P01")
        return "ok"

    assert view() == "ok"
    assert len(calls) == 2


def test_other_database_errors_are_not_retried():
    calls = []

    @retry_on_serialization_failure
    def view():
        calls.append(1)
        raise _pg_error("23505")  # unique_violation, not transient

    with pytest.raises(OperationalError):
        view()
    # Non-retryable errors propagate immediately without a second attempt.
    assert len(calls) == 1
