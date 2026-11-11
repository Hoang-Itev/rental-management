"""Guard room.property_id against floor/building property ownership drift.

Database Design V3 shape unchanged: triggers, not new tables.
"""
from alembic import op, context
import sqlalchemy as sa

revision = "room_v3_002"
down_revision = "room_v3_001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    inconsistent = None
    if not context.is_offline_mode():
        bind = op.get_bind()
        inconsistent = bind.execute(sa.text(
            "SELECT r.id FROM rooms r "
        "JOIN floors f ON f.id = r.floor_id "
        "JOIN buildings b ON b.id = f.building_id "
            "WHERE r.property_id IS DISTINCT FROM b.property_id LIMIT 1"
        )).first()
    if inconsistent is not None:
        raise RuntimeError(
            "rooms has a property/floor ownership mismatch. "
            "Correct it before applying room_v3_002. "
            f"Example room_id={inconsistent.id}"
        )
    op.execute("""
    CREATE FUNCTION rm_guard_room_property() RETURNS trigger AS $$
    DECLARE actual_property uuid;
    BEGIN
      SELECT b.property_id INTO actual_property
      FROM floors f JOIN buildings b ON b.id = f.building_id
      WHERE f.id = NEW.floor_id;
      IF actual_property IS DISTINCT FROM NEW.property_id THEN
        RAISE EXCEPTION 'room.property_id must match floor building property'
          USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER trg_room_property_matches_floor
    BEFORE INSERT OR UPDATE OF property_id, floor_id ON rooms
    FOR EACH ROW EXECUTE FUNCTION rm_guard_room_property();
    """)
    op.execute("""
    CREATE FUNCTION rm_guard_building_move() RETURNS trigger AS $$
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
    CREATE TRIGGER trg_guard_building_property_move
    BEFORE UPDATE OF property_id ON buildings
    FOR EACH ROW EXECUTE FUNCTION rm_guard_building_move();
    """)
    op.execute("""
    CREATE FUNCTION rm_guard_floor_move() RETURNS trigger AS $$
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
    op.execute("""
    CREATE TRIGGER trg_guard_floor_building_move
    BEFORE UPDATE OF building_id ON floors
    FOR EACH ROW EXECUTE FUNCTION rm_guard_floor_move();
    """)

def downgrade() -> None:
    op.execute('DROP TRIGGER IF EXISTS trg_guard_floor_building_move ON floors')
    op.execute('DROP TRIGGER IF EXISTS trg_guard_building_property_move ON buildings')
    op.execute('DROP TRIGGER IF EXISTS trg_room_property_matches_floor ON rooms')
    op.execute('DROP FUNCTION IF EXISTS rm_guard_floor_move()')
    op.execute('DROP FUNCTION IF EXISTS rm_guard_building_move()')
    op.execute('DROP FUNCTION IF EXISTS rm_guard_room_property()')
