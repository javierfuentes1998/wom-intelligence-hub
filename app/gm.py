from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DB

from .models import GameMasterRate, Room, Session


def rate_record(db: DB, location_id: str, on_date: date, room_id=None, rate_type="normal"):
    """Return the exact effective rate row, preferring a room-specific rule."""
    return db.scalar(select(GameMasterRate).where(
        GameMasterRate.location_id == location_id,
        GameMasterRate.rate_type == rate_type,
        GameMasterRate.valid_from <= on_date,
        or_(GameMasterRate.valid_to == None, GameMasterRate.valid_to >= on_date),
        or_(GameMasterRate.room_id == room_id, GameMasterRate.room_id == None),
        GameMasterRate.active == True,
    ).order_by(GameMasterRate.room_id.desc(), GameMasterRate.valid_from.desc()))


def rate_for(db: DB, location_id: str, on_date: date, room_id=None, rate_type="normal"):
    rate = rate_record(db, location_id, on_date, room_id, rate_type)
    return rate.amount if rate else None


def infer_double(room_id: str, starts: list[datetime], threshold_minutes=90):
    """DEMO proximity model: mark both ends of every SOTANO link symmetrically.

    The model uses the existing 90-minute operational threshold because historical
    end times are not available. It can later be replaced by interval intersection.
    """
    if room_id != "SOTANO":
        return set()
    ordered = sorted(starts)
    flagged = set()
    for a, b in zip(ordered, ordered[1:]):
        if 0 < (b - a).total_seconds() / 60 <= threshold_minutes:
            flagged |= {a, b}
    return flagged


def infer_double_evidence(room_id: str, sessions: list[Session], threshold_minutes=90):
    """Return symmetric overlap evidence by session id for connected DEMO slots."""
    if room_id != "SOTANO":
        return {}
    evidence = defaultdict(list)
    by_day = defaultdict(list)
    for session in sessions:
        if session.room_id != "SOTANO":
            continue
        by_day[session.starts_at.date()].append(session)
    for day_sessions in by_day.values():
        ordered = sorted(day_sessions, key=lambda row: (row.starts_at, row.id))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1:]:
                minutes = (right.starts_at - left.starts_at).total_seconds() / 60
                if minutes > threshold_minutes:
                    break
                if minutes <= 0:
                    continue
                criterion = f"proximidad DEMO <= {threshold_minutes} minutos"
                evidence[left.id].append({"session_id": right.id, "time": right.starts_at.strftime("%H:%M"), "minutes": int(minutes), "criterion": criterion})
                evidence[right.id].append({"session_id": left.id, "time": left.starts_at.strftime("%H:%M"), "minutes": int(minutes), "criterion": criterion})
    return dict(evidence)


def _double_state(session: Session, inferred_evidence: dict):
    source = (session.double_gm_source or "").upper()
    if session.requires_double_gm and source in {"CONFIRMED", "EXPLICIT"}:
        return "double", "confirmed"
    if session.id in inferred_evidence:
        return "double", "inferred"
    return "normal", None


def gm_summary(db: DB, gm_id: str, start: date, end: date, location_id=None, room_id=None):
    query = select(Session, Room).join(Room, Room.id == Session.room_id).where(
        or_(Session.game_master_id == gm_id, Session.second_game_master_id == gm_id),
        Session.starts_at >= start,
        Session.starts_at < end + timedelta(days=1),
        Session.status == "completed",
    )
    if location_id:
        query = query.where(Room.location_id == location_id)
    if room_id:
        query = query.where(Room.id == room_id)
    rows = db.execute(query.order_by(Session.starts_at, Session.id)).all()

    # Inference is a property of SOTANO operations, not of one GM's subset.
    # Therefore all completed SOTANO sessions in the period participate.
    sotano_sessions = db.scalars(select(Session).where(
        Session.room_id == "SOTANO", Session.status == "completed",
        Session.starts_at >= start, Session.starts_at < end + timedelta(days=1),
    )).all()
    inferred_evidence = infer_double_evidence("SOTANO", sotano_sessions)

    details = []
    for session, room in rows:
        session_type, double_status = _double_state(session, inferred_evidence)
        rate = rate_record(db, room.location_id, session.starts_at.date(), room.id, session_type)
        details.append({
            "gm_id": gm_id, "session_id": session.id,
            "date": session.starts_at.date(), "time": session.starts_at.strftime("%H:%M"),
            "location_id": room.location_id, "room_id": room.id, "room": room.name,
            "session_type": session_type, "type": session_type,
            "double_status": double_status, "double_source": double_status,
            "overlap_evidence": inferred_evidence.get(session.id, []) if double_status == "inferred" else [],
            "inference_model": "DEMO proximity <= 90 minutes; replace with start_A < end_B AND start_B < end_A when end times exist" if double_status == "inferred" else None,
            "players": session.customers,
            "rate_id": rate.id if rate else None, "rate_amount": rate.amount if rate else None,
            "rate_valid_from": rate.valid_from if rate else None, "rate_valid_to": rate.valid_to if rate else None,
            "calculated_amount": rate.amount if rate else None, "pay": rate.amount if rate else None,
            "source": session.source_system,
        })

    groups = defaultdict(lambda: {"sessions": 0, "subtotal": 0.0, "room_ids": set()})
    for item in details:
        if item["rate_amount"] is None:
            continue
        key = (item["location_id"], item["session_type"], item["rate_amount"], item["rate_valid_from"], item["rate_valid_to"])
        groups[key]["sessions"] += 1
        groups[key]["subtotal"] += item["calculated_amount"]
        groups[key]["room_ids"].add(item["room_id"])
    breakdown = [{
        "location_id": key[0], "room_id": next(iter(value["room_ids"])) if len(value["room_ids"]) == 1 else None,
        "room_ids": sorted(value["room_ids"]), "session_type": key[1],
        "rate_amount": key[2], "rate_valid_from": key[3], "rate_valid_to": key[4],
        "sessions": value["sessions"], "subtotal": round(value["subtotal"], 2),
    } for key, value in groups.items()]
    missing_rate = sum(item["rate_amount"] is None for item in details)
    players = sum(item["players"] for item in details)
    return {
        "gm_id": gm_id, "scope": {"start": start, "end": end, "location_id": location_id, "room_id": room_id},
        "sessions": len(details), "normal": sum(item["session_type"] == "normal" for item in details),
        "double": sum(item["session_type"] == "double" for item in details),
        "customers": players, "players": players,
        "estimated_pay": None if missing_rate else round(sum(item["calculated_amount"] for item in details), 2),
        "pay_complete": missing_rate == 0, "missing_rate_sessions": missing_rate,
        "pay_breakdown": breakdown, "details": details,
    }
