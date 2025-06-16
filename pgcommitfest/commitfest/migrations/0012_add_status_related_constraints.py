from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("commitfest", "0011_add_draft_remove_future"),
    ]
    operations = [
        migrations.RunSQL(
            """
CREATE UNIQUE INDEX cf_enforce_maxoneopen_idx
ON commitfest_commitfest (status, draft)
WHERE status not in (1,4);
""",
            reverse_sql="""
DROP INDEX IF EXISTS cf_enforce_maxoneopen_idx;
""",
        ),
        migrations.RunSQL(
            """
WITH cte AS (
    SELECT * FROM (
        SELECT
            id,
            patch_id,
            status,
            ROW_NUMBER() OVER (PARTITION BY patch_id ORDER BY commitfest_id DESC) AS rn
        FROM
            commitfest_patchoncommitfest
        WHERE
            status NOT IN (5)
    ) q
    WHERE rn > 1
)
UPDATE commitfest_patchoncommitfest
SET status = 5
WHERE id IN (
    SELECT id
    FROM cte
);
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
UPDATE commitfest_patchoncommitfest
SET leavedate =
    CASE
        WHEN status IN (4,5,6,7,8) THEN NOW()
        ELSE NULL
    END
WHERE
    (status IN (4,5,6,7,8) AND leavedate IS NULL)
    OR (status NOT IN (4,5,6,7,8) AND leavedate IS NOT NULL);
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
