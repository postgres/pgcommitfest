from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("commitfest", "0010_add_failing_since_column"),
    ]
    operations = [
        migrations.RunSQL(
            """
CREATE UNIQUE INDEX cf_enforce_maxoneopen_idx
ON commitfest_commitfest (status)
WHERE status not in (1,4);
""",
            reverse_sql="""
DROP INDEX IF EXISTS cf_enforce_maxoneopen_idx;
""",
        ),
        migrations.RunSQL(
            """
CREATE UNIQUE INDEX poc_enforce_maxoneoutcome_idx
ON commitfest_patchoncommitfest (patch_id)
WHERE status not in (5);
""",
            reverse_sql="""
DROP INDEX IF EXISTS poc_enforce_maxoneoutcome_idx;
""",
        ),
        migrations.RunSQL(
            """
ALTER TABLE commitfest_patchoncommitfest
ADD CONSTRAINT status_and_leavedate_correlation
CHECK ((status IN (4,5,6,7,8)) = (leavedate IS NOT NULL));
""",
            reverse_sql="""
ALTER TABLE commitfest_patchoncommitfest
DROP CONSTRAINT IF EXISTS status_and_leavedate_correlation;
""",
        ),
        migrations.RunSQL(
            """
COMMENT ON COLUMN commitfest_patchoncommitfest.leavedate IS
$$A leave date is recorded in two situations, both of which
means this particular patch-cf combination became inactive
on the corresponding date.  For status 5 the patch was moved
to some other cf.  For 4,6,7, and 8, this was the final cf.
$$
""",
            reverse_sql="""
COMMENT ON COLUMN commitfest_patchoncommitfest.leavedate IS NULL;
""",
        ),
        migrations.RunSQL(
            """
COMMENT ON TABLE commitfest_patchoncommitfest IS
$$This is a re-entrant table: patches may become associated
with a given cf multiple times, resetting the entrydate and clearing
the leavedate each time.  Non-final statuses never have a leavedate
while final statuses always do.  The final status of 5 (moved) is
special in that all but one of the rows a patch has in this table
must have it as the status.
$$
""",
            reverse_sql="""
COMMENT ON TABLE commitfest_patchoncommitfest IS NULL;
""",
        ),
    ]
