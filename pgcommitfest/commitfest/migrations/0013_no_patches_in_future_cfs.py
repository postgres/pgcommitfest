from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("commitfest", "0012_add_parked_cf_status"),
    ]
    operations = [
        migrations.RunSQL("""
CREATE FUNCTION assert_poc_not_future_for_poc()
RETURNS TRIGGER AS $$
DECLARE
    cfstatus int;
BEGIN
    SELECT status INTO cfstatus
    FROM commitfest_commitfest
    WHERE id = NEW.commitfest_id;

    IF cfstatus = 1 THEN
       RAISE EXCEPTION 'Patches cannot exist on future commitfests';
    END IF;

    RETURN NEW;
END;
$$
LANGUAGE plpgsql;

CREATE FUNCTION assert_poc_not_future_for_cf()
RETURNS trigger AS $$
BEGIN
    -- Trigger checks that we only get called when status is 1
    PERFORM 1
    FROM commitfest_patchoncommitfest
    WHERE commitfest_id = NEW.id
    LIMIT 1;

    IF FOUND THEN
       RAISE EXCEPTION 'Cannot change commitfest status to 1, patches exists.';
    END IF;
    RETURN NEW;
END;
$$
LANGUAGE plpgsql;

CREATE TRIGGER assert_poc_commitfest_is_not_future
BEFORE INSERT OR UPDATE ON commitfest_patchoncommitfest
FOR EACH ROW
EXECUTE FUNCTION assert_poc_not_future_for_poc();

CREATE TRIGGER assert_poc_commitfest_is_not_future
-- Newly inserted cfs can't have patches
BEFORE UPDATE ON commitfest_commitfest
FOR EACH ROW
WHEN (NEW.status = 1)
EXECUTE FUNCTION assert_poc_not_future_for_cf();
"""),
    ]
