from django.contrib.auth.models import User

from datetime import datetime

import pytest

from pgcommitfest.commitfest.models import Committer, Patch, PatchOnCommitFest, Tag

# The commitfest views start with SET TRANSACTION ISOLATION LEVEL, which must
# be the first statement in a transaction, so the test can't wrap them in one.
pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


def make_committer(username, first_name, last_name, active=True):
    user = User.objects.create_user(
        username=username, first_name=first_name, last_name=last_name
    )
    return Committer.objects.create(user=user, active=active)


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


def get_patch_names(client, cf, **params):
    response = client.get(f"/{cf.id}/", params)
    assert response.status_code == 200
    return [p["name"] for p in response.context["patches"]]


@pytest.fixture
def cf(commitfests):
    # Rendering pages needs the full set of relevant commitfests to exist.
    return commitfests["open"]


@pytest.fixture
def committers():
    return {
        "adams": make_committer("zadams", "Zed", "Adams"),
        "young": make_committer("ayoung", "Amy", "Young"),
    }


@pytest.fixture
def filter_patches(cf, committers):
    make_patch(cf, "adams-open", committers["adams"])
    make_patch(
        cf,
        "adams-committed",
        committers["adams"],
        status=PatchOnCommitFest.STATUS_COMMITTED,
    )
    make_patch(
        cf,
        "young-committed",
        committers["young"],
        status=PatchOnCommitFest.STATUS_COMMITTED,
    )
    make_patch(cf, "none-open", None)


def test_filter_by_committer(client, cf, committers, filter_patches):
    adams = committers["adams"].user_id
    assert get_patch_names(client, cf, committer=adams) == [
        "adams-open",
        "adams-committed",
    ]


def test_filter_by_committer_and_committed_status(
    client, cf, committers, filter_patches
):
    adams = committers["adams"].user_id
    assert get_patch_names(
        client, cf, committer=adams, status=PatchOnCommitFest.STATUS_COMMITTED
    ) == ["adams-committed"]


def test_filter_by_committer_combined_with_sort(client, cf, committers):
    adams = committers["adams"]
    other = make_committer("bsmith", "Bea", "Smith")
    make_patch(cf, "adams-1", adams, status=PatchOnCommitFest.STATUS_COMMITTED)
    make_patch(cf, "other", other, status=PatchOnCommitFest.STATUS_COMMITTED)
    make_patch(cf, "adams-2", adams, status=PatchOnCommitFest.STATUS_COMMITTED)

    response = client.get(
        f"/{cf.id}/",
        {
            "committer": adams.user_id,
            "status": PatchOnCommitFest.STATUS_COMMITTED,
            "sortkey": -9,
        },
    )
    assert response.status_code == 200
    assert response.context["sortkey"] == -9
    assert [p["name"] for p in response.context["patches"]] == [
        "adams-1",
        "adams-2",
    ]


def test_filter_all_committers(client, cf, filter_patches):
    # "* All" with no other filters is the same as the plain page
    response = client.get(f"/{cf.id}/", {"committer": "-1"})
    assert response.status_code == 302
    assert response["Location"] == f"/{cf.id}/"

    assert get_patch_names(client, cf, committer="-1", sortkey=9) == [
        "adams-open",
        "none-open",
        "adams-committed",
        "young-committed",
    ]


def test_filter_combines_with_author_and_tag(client, cf, committers, alice):
    tag = Tag.objects.create(name="Committer test", color="#000000")
    adams = committers["adams"]
    match = make_patch(cf, "match", adams)
    match.authors.add(alice)
    match.tags.add(tag)
    no_tag = make_patch(cf, "no-tag", adams)
    no_tag.authors.add(alice)
    wrong_committer = make_patch(cf, "wrong-committer", committers["young"])
    wrong_committer.authors.add(alice)
    wrong_committer.tags.add(tag)

    assert get_patch_names(
        client, cf, committer=adams.user_id, author=alice.id, tag=tag.id
    ) == ["match"]


@pytest.fixture
def other_cf_committer(commitfests):
    committer = make_committer("bsmith", "Bea", "Smith")
    make_patch(commitfests["in_progress"], "elsewhere", committer)
    return committer


@pytest.mark.parametrize(
    "value",
    ["abc", "", "1.5", "other-cf", "no-patches", "999999", str(2**40), str(10**30)],
)
def test_invalid_committer_is_ignored(
    client, cf, committers, filter_patches, other_cf_committer, value
):
    if value == "other-cf":
        value = other_cf_committer.user_id
    elif value == "no-patches":
        value = make_committer("nnone", "Ned", "None").user_id

    # Without other filters, the parameter is ignored and stripped
    response = client.get(f"/{cf.id}/", {"committer": value})
    assert response.status_code == 302
    assert response["Location"] == f"/{cf.id}/"

    assert get_patch_names(client, cf, committer=value, sortkey=4) == [
        "adams-open",
        "none-open",
        "adams-committed",
        "young-committed",
    ]


def test_committer_choices(client, commitfests, cf, committers, filter_patches):
    inactive = make_committer("iold", "Ian", "Old", active=False)
    make_patch(cf, "inactive", inactive, status=PatchOnCommitFest.STATUS_COMMITTED)
    # Committers without patches in this commitfest are not offered
    elsewhere = make_committer("eelse", "Eve", "Elsewhere")
    make_patch(commitfests["in_progress"], "elsewhere", elsewhere)
    make_committer("nnone", "Ned", "None")
    # Users that are not committers are not offered either
    author = User.objects.create_user(username="author", last_name="Author")
    make_patch(cf, "authored", None).authors.add(author)

    response = client.get(f"/{cf.id}/")
    form = response.context["form"]
    # Sorted by first name, like the names are shown
    assert form.fields["committer"].choices == [
        (-1, "* All"),
        (committers["young"].user_id, "Amy Young (ayoung)"),
        (inactive.user_id, "Ian Old (iold)"),
        (committers["adams"].user_id, "Zed Adams (zadams)"),
    ]
    # A plain dropdown, not a searchable one
    assert b'<select name="committer"' in response.content
    assert "committer" not in form.selectize_fields
    assert b"#id_committer" not in response.content


def test_committer_filter_not_shown_on_dashboard(client, cf, alice):
    client.force_login(alice)
    response = client.get("/")
    assert response.status_code == 200
    form = response.context["form"]
    assert "committer" not in form.fields
    assert "committer" not in form.selectize_fields
    assert b'name="committer"' not in response.content


def test_committer_filter_not_applied_on_dashboard(
    client, commitfests, committers, alice
):
    in_progress = commitfests["in_progress"]
    adams = make_patch(in_progress, "adams", committers["adams"])
    adams.authors.add(alice)
    young = make_patch(in_progress, "young", committers["young"])
    young.authors.add(alice)
    client.force_login(alice)

    # Without other filters, the parameter is ignored and stripped
    response = client.get("/", {"committer": committers["adams"].user_id})
    assert response.status_code == 302

    response = client.get(
        "/",
        {
            "committer": committers["adams"].user_id,
            "status": PatchOnCommitFest.STATUS_REVIEW,
        },
    )
    assert response.status_code == 200
    assert sorted(p["name"] for p in response.context["patches"]) == [
        "adams",
        "young",
    ]


def test_committer_filter_not_shown_on_global_search(client, cf, alice):
    client.force_login(alice)
    response = client.get("/search/", {"searchterm": "anything"})
    assert response.status_code == 200
    form = response.context["form"]
    assert "committer" not in form.fields
    assert "committer" not in form.selectize_fields
    assert b'name="committer"' not in response.content
