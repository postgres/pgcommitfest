from django.db import migrations


def undo_pg19_final_close(apps, schema_editor):
    CommitFest = apps.get_model("commitfest", "CommitFest")
    PatchOnCommitFest = apps.get_model("commitfest", "PatchOnCommitFest")
    PatchHistory = apps.get_model("commitfest", "PatchHistory")

    STATUS_INPROGRESS = 3
    STATUS_CLOSED = 4
    STATUS_MOVED = 5

    try:
        pg19_final = CommitFest.objects.get(name="PG19-Final")
    except CommitFest.DoesNotExist:
        # Not running against a database that has PG19-Final
        return

    if pg19_final.status != STATUS_CLOSED:
        return

    # Find patches that were auto-moved by cfbot when the commitfest closed.
    # These have PatchHistory entries with by_cfbot=True.
    moved_histories = PatchHistory.objects.filter(
        by_cfbot=True,
        what__startswith=f"Moved from CF {pg19_final.name} to CF ",
    )

    moved_patch_ids = set(moved_histories.values_list("patch_id", flat=True))

    for patch_id in moved_patch_ids:
        # Get the PatchOnCommitFest in PG19-Final (should be STATUS_MOVED)
        try:
            old_poc = PatchOnCommitFest.objects.get(
                patch_id=patch_id, commitfest=pg19_final
            )
        except PatchOnCommitFest.DoesNotExist:
            continue

        if old_poc.status != STATUS_MOVED:
            continue

        # Find the new PatchOnCommitFest that was created by the move. The
        # move preserves the original status, so we can read it from there.
        new_poc = (
            PatchOnCommitFest.objects.filter(patch_id=patch_id)
            .exclude(commitfest=pg19_final)
            .order_by("-enterdate")
            .first()
        )

        if new_poc is None:
            continue

        # Restore the old poc to its original status
        old_poc.status = new_poc.status
        old_poc.leavedate = None
        old_poc.save()

        # Remove the new poc that was created by the move
        new_poc.delete()

    # Delete the PatchHistory entries for these moves
    moved_histories.delete()

    # Reopen the commitfest and fix the end date
    pg19_final.status = STATUS_INPROGRESS
    pg19_final.enddate = "2026-04-09"
    pg19_final.save()


class Migration(migrations.Migration):
    dependencies = [
        ("commitfest", "0017_make_topic_optional"),
    ]

    operations = [
        migrations.RunPython(undo_pg19_final_close, migrations.RunPython.noop),
    ]
