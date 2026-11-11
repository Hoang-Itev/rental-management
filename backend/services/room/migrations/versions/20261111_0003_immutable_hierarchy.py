"""Make building/floor parents immutable to prevent concurrent ownership drift.

A building may not be reparented to another property, and a floor may not
be moved to another building even before it has any rooms. The prior 002
triggers checked for existing rooms and permitted a concurrent write skew.

No tables are added. Existing records remain untouched.
"""
from alembic import op

revision = "room_v3_003"
down_revision = "room_v3_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reuse the trigger names installed in 002. Changing a parent key is never
    # a supported business operation; no SELECT/EXISTS or row race remains.
    op.execute("""
    CREATE OR REPLACE FUNCTION rm_guard_building_move() RETURNS trigger AS $$
    BEGIN
      IF NEW.property_id IS DISTINCT FROM OLD.property_id THEN
        RAISE EXCEPTION 'building.property_id is immutable after creation'
          USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION rm_guard_floor_move() RETURNS trigger AS $$
    BEGIN
      IF NEW.building_id IS DISTINCT FROM OLD.building_id THEN
        RAISE EXCEPTION 'floor.building_id is immutable after creation'
          USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # Restore the exact 002 behavior if rolling back. That behavior has a
    # concurrency weakness, so downgrading is not recommended for production.
    op.execute("""
    CREATE OR REPLACE FUNCTION rm_guard_building_move() RETURNS trigger AS $$
    BEGIN
      IF NEW.property_id IS DISTINCT FROM OLD.property_id AND EXISTS (
        SELECT 1 FROM floors f JOIN rooms r ON r.floor_id = f.id
        WHERE f.building_id = OLD.id
      ) THEN
        RAISE EXCEPTION 'cannot move building with existing rooms across properties'
          USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION rm_guard_floor_move() RETURNS trigger AS $$
    BEGIN
      IF NEW.building_id IS DISTINCT FROM OLD.building_id AND EXISTS (
        SELECT 1 FROM rooms WHERE floor_id = OLD.id
      ) THEN
        RAISE EXCEPTION 'cannot move a floor with rooms to another building'
          USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    """)
