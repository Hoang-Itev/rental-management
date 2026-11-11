from uuid import uuid4

def example(room=None, event=None):
    room = room or uuid4()
    return {
        "event_id": str(event or uuid4()), "event_type": "RoomCreated", "event_version": 1,
        "occurred_at": "2026-11-11T10:00:00+00:00", "correlation_id": str(uuid4()),
        "aggregate_id": str(room), "data": {"room_id": str(room), "property_id": str(uuid4()),
                                        "floor_id": str(uuid4()), "room_code": "A101"},
        "_batch": {"private": True},
    }
