from django.contrib.auth.models import User

from datetime import datetime

import pytest

from pgcommitfest.commitfest.models import Committer, Patch, PatchOnCommitFest

# The commitfest views start with SET TRANSACTION ISOLATION LEVEL, which must
# be the first statement in a transaction, so the test can't wrap them in one.
pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


def make_committer(username, first_name, last_name):
    user = User.objects.create_user(
        username=username, first_name=first_name, last_name=last_name
    )
    return Committer.objects.create(user=user)


def make_patch(cf, name, committer=None, status=PatchOnCommitFest.STATUS_REVIEW):
    patch = Patch.objects.create(name=name, committer=committer)
    is_open = status in PatchOnCommitFest.OPEN_STATUSES
    PatchOnCommitFest.objects.create(
        patch=patch,
        commitfest=cf,
        enterdate=datetime.now(),
        leavedate=None if is_open else datetime.now(),
        status=status,
    )
    return patch


def patch_names(client, cf, **params):
    response = client.get(f"/{cf.id}/", params)
    assert response.status_code == 200
    return [p["name"] for p in response.context["patches"]]


@pytest.fixture
def cf(commitfests):
    # Rendering pages needs the full set of relevant commitfests to exist.
    return commitfests["open"]


@pytest.fixture
def committers():
    # Surnames are chosen so that sorting by first name would give the
    # reverse of sorting by surname.
    return {
        "adams": make_committer("zadams", "Zed", "Adams"),
        "moore": make_committer("mmoore", "Mia", "Moore"),
        "young": make_committer("ayoung", "Amy", "Young"),
    }


@pytest.fixture
def sort_patches(cf, committers):
    # Created in an order that matches neither sort direction.
    make_patch(cf, "moore", committers["moore"])
    make_patch(cf, "none", None)
    make_patch(cf, "young", committers["young"])
    make_patch(cf, "adams", committers["adams"])


def test_sort_by_committer_ascending(client, cf, sort_patches):
    assert patch_names(client, cf, sortkey=9) == [
        "adams",
        "moore",
        "young",
        "none",
    ]


def test_sort_by_committer_descending(client, cf, sort_patches):
    assert patch_names(client, cf, sortkey=-9) == [
        "young",
        "moore",
        "adams",
        "none",
    ]


def test_sort_by_committer_tiebreakers(client, cf):
    bea = make_committer("bsmith", "Bea", "Smith")
    ann2 = make_committer("asmith2", "Ann", "Smith")
    ann1 = make_committer("asmith1", "Ann", "Smith")

    make_patch(cf, "bea", bea)
    first = make_patch(cf, "ann2-a", ann2)
    second = make_patch(cf, "ann2-b", ann2)
    make_patch(cf, "ann1", ann1)
    assert first.id < second.id

    assert patch_names(client, cf, sortkey=9) == [
        "ann1",
        "ann2-a",
        "ann2-b",
        "bea",
    ]
    # The names are reversed, but the patch id stays ascending as a tiebreaker
    assert patch_names(client, cf, sortkey=-9) == [
        "bea",
        "ann2-a",
        "ann2-b",
        "ann1",
    ]


def test_sort_by_committer_keeps_open_patches_first(client, cf, committers):
    make_patch(
        cf,
        "adams-committed",
        committers["adams"],
        status=PatchOnCommitFest.STATUS_COMMITTED,
    )
    make_patch(cf, "young-open", committers["young"])
    make_patch(cf, "none-open", None)
    make_patch(
        cf,
        "moore-committed",
        committers["moore"],
        status=PatchOnCommitFest.STATUS_COMMITTED,
    )

    assert patch_names(client, cf, sortkey=9) == [
        "young-open",
        "none-open",
        "adams-committed",
        "moore-committed",
    ]
    assert patch_names(client, cf, sortkey=-9) == [
        "young-open",
        "none-open",
        "moore-committed",
        "adams-committed",
    ]


def test_sort_by_committer_with_committed_status_filter(client, cf, committers):
    for name in ("young", "adams", "moore"):
        make_patch(
            cf, name, committers[name], status=PatchOnCommitFest.STATUS_COMMITTED
        )
    make_patch(cf, "open", committers["adams"])

    assert patch_names(
        client, cf, sortkey=9, status=PatchOnCommitFest.STATUS_COMMITTED
    ) == ["adams", "moore", "young"]


def test_default_order_is_unchanged(client, cf, sort_patches):
    assert patch_names(client, cf) == ["moore", "none", "young", "adams"]


@pytest.mark.parametrize("sortkey", ["0", "99", "abc"])
def test_unknown_sortkey_redirects_to_default(client, cf, sortkey):
    response = client.get(f"/{cf.id}/", {"sortkey": sortkey})
    assert response.status_code == 302
    assert response["Location"] == f"/{cf.id}/"


def test_committer_header_is_sortable(client, cf, sort_patches):
    response = client.get(f"/{cf.id}/")
    assert b'onclick="return sortpatches(9);">Committer</a>' in response.content

    response = client.get(f"/{cf.id}/", {"sortkey": 9})
    assert response.context["sortkey"] == 9
    assert b"bi-sort-alpha-down" in response.content

    response = client.get(f"/{cf.id}/", {"sortkey": -9})
    assert response.context["sortkey"] == -9
    assert b"bi-sort-alpha-up" in response.content


def test_dashboard_does_not_sort_by_committer(client, cf, alice, committers):
    patch = make_patch(cf, "mine", committers["adams"])
    patch.authors.add(alice)
    client.force_login(alice)

    # Without other filters, an unsupported sortkey redirects to the plain page
    response = client.get("/", {"sortkey": 9})
    assert response.status_code == 302

    response = client.get(
        "/", {"sortkey": 9, "status": PatchOnCommitFest.STATUS_REVIEW}
    )
    assert response.status_code == 200
    assert response.context["sortkey"] == 0
