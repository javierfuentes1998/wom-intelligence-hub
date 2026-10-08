from datetime import date, datetime
from pathlib import Path

import pytest

from app.gm import gm_summary, infer_double_evidence
from app.models import GameMaster, GameMasterRate, Location, Room, Session


def setup_dimensions(db):
    db.add_all([
        Location(id="LA_FLORIDA", name="Florida"), Location(id="ALTOZANO", name="Altozano"),
        Location(id="LOS_ANGELES", name="Los Ángeles"), Location(id="ORIHUELA", name="Orihuela"),
    ])
    db.flush()
    db.add_all([
        Room(id="SOTANO", location_id="LA_FLORIDA", name="El Sótano", capacity=8),
        Room(id="HAMMER", location_id="LA_FLORIDA", name="Hammer Killer", capacity=8),
        Room(id="YUCATAN", location_id="ALTOZANO", name="Yucatán", capacity=8),
        Room(id="SEMILLAS", location_id="LOS_ANGELES", name="Las Semillas", capacity=8),
        Room(id="PESADILLAS_II", location_id="ORIHUELA", name="Pesadillas II", capacity=8),
        GameMaster(id="GM-JAVI", display_name="Aster", home_location_id="LA_FLORIDA"),
        GameMaster(id="GM-JAVI-ESPIN", display_name="Lumera", home_location_id="LOS_ANGELES"),
    ])
    db.flush()
    for location, amount in [("LA_FLORIDA", 20), ("ALTOZANO", 18), ("LOS_ANGELES", 20), ("ORIHUELA", 25)]:
        db.add(GameMasterRate(location_id=location, amount=amount, rate_type="normal", valid_from=date(2020, 1, 1)))
    db.add(GameMasterRate(location_id="LA_FLORIDA", room_id="SOTANO", amount=26, rate_type="double", valid_from=date(2020, 1, 1)))
    db.commit()


def test_scope_reconciliation_and_traceability(db):
    setup_dimensions(db)
    db.add_all([
        Session(id="N", room_id="HAMMER", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 2, 18), status="completed", customers=4, source_system="DEMO"),
        Session(id="D", room_id="SOTANO", game_master_id="GM-JAVI", second_game_master_id="GM-JAVI-ESPIN", starts_at=datetime(2026, 9, 3, 18), status="completed", customers=6, requires_double_gm=True, double_gm_source="CONFIRMED", source_system="DEMO"),
        Session(id="O", room_id="YUCATAN", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 4, 18), status="completed", customers=5, source_system="DEMO"),
    ])
    db.commit()
    result = gm_summary(db, "GM-JAVI", date(2026, 9, 1), date(2026, 9, 30), "LA_FLORIDA")
    assert result["sessions"] == result["normal"] + result["double"] == 2
    assert result["players"] == sum(row["players"] for row in result["details"]) == 10
    assert result["estimated_pay"] == sum(row["calculated_amount"] for row in result["details"]) == 46
    assert sum(row["subtotal"] for row in result["pay_breakdown"]) == 46
    assert {"gm_id", "session_id", "room_id", "rate_id", "rate_valid_from", "source"} <= result["details"][0].keys()


def test_javi_and_javi_espin_are_distinct_ids(db):
    setup_dimensions(db)
    db.add_all([
        Session(id="J", room_id="HAMMER", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 1, 18), status="completed", customers=4),
        Session(id="JE", room_id="SEMILLAS", game_master_id="GM-JAVI-ESPIN", starts_at=datetime(2026, 9, 1, 18), status="completed", customers=5),
    ])
    db.commit()
    javi = gm_summary(db, "GM-JAVI", date(2026, 9, 1), date(2026, 9, 30))
    espin = gm_summary(db, "GM-JAVI-ESPIN", date(2026, 9, 1), date(2026, 9, 30))
    assert [row["session_id"] for row in javi["details"]] == ["J"]
    assert [row["session_id"] for row in espin["details"]] == ["JE"]
    assert espin["estimated_pay"] == 20


def test_explicit_double_has_priority_and_inference_is_sotano_only(db):
    setup_dimensions(db)
    db.add_all([
        Session(id="C", room_id="SOTANO", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 1, 18), status="completed", customers=4, requires_double_gm=True, double_gm_source="CONFIRMED"),
        Session(id="I", room_id="SOTANO", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 1, 19), status="completed", customers=5),
        Session(id="H1", room_id="HAMMER", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 2, 18), status="completed", customers=3),
        Session(id="H2", room_id="HAMMER", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 2, 19), status="completed", customers=3),
    ])
    db.commit()
    result = gm_summary(db, "GM-JAVI", date(2026, 9, 1), date(2026, 9, 30))
    states = {row["session_id"]: (row["session_type"], row["double_status"]) for row in result["details"]}
    assert states == {"C": ("double", "confirmed"), "I": ("double", "inferred"), "H1": ("normal", None), "H2": ("normal", None)}
    assert next(row for row in result["details"] if row["session_id"] == "C")["rate_amount"] == 26


def test_historical_rate_and_missing_rate_are_not_faked(db):
    setup_dimensions(db)
    db.add(GameMasterRate(location_id="ALTOZANO", amount=21, rate_type="normal", valid_from=date(2027, 1, 1)))
    db.add_all([
        Session(id="OLD", room_id="YUCATAN", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 1, 18), status="completed", customers=3),
        Session(id="NEW", room_id="YUCATAN", game_master_id="GM-JAVI", starts_at=datetime(2027, 2, 1, 18), status="completed", customers=3),
    ])
    db.commit()
    old = gm_summary(db, "GM-JAVI", date(2026, 9, 1), date(2026, 9, 30))
    new = gm_summary(db, "GM-JAVI", date(2027, 2, 1), date(2027, 2, 28))
    assert old["estimated_pay"] == 18 and new["estimated_pay"] == 21
    db.query(GameMasterRate).filter(GameMasterRate.location_id == "ALTOZANO").delete()
    db.commit()
    missing = gm_summary(db, "GM-JAVI", date(2026, 9, 1), date(2026, 9, 30))
    assert missing["estimated_pay"] is None and not missing["pay_complete"] and missing["missing_rate_sessions"] == 1


def test_api_filters_and_rejects_incompatible_room(client, db):
    setup_dimensions(db)
    db.add(Session(id="A", room_id="YUCATAN", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 1, 18), status="completed", customers=3))
    db.commit()
    url = "/api/game-masters/GM-JAVI/summary?start=2026-09-01&end=2026-09-30"
    assert client.get(url + "&location_id=ALTOZANO&room_id=YUCATAN").json()["sessions"] == 1
    assert client.get(url + "&location_id=LA_FLORIDA&room_id=YUCATAN").status_code == 422
    assert client.get(url + "&location_id=ORIHUELA").json()["sessions"] == 0


@pytest.mark.parametrize("fragment", [
    "Jugadores atendidos", "¿Cómo se calcula esta remuneración?", "¿Cómo interpretar este análisis?",
    "Doble · ${d.double_status==='confirmed'?'confirmada':'inferida'}", "no evaluación laboral",
    "Estos filtros buscan dentro del detalle y no modifican los KPI superiores",
])
def test_frontend_explainability_and_spanish_terms(fragment):
    source = (Path(__file__).parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")
    assert fragment in source


def test_no_worker_rankings_or_scores_added():
    source = (Path(__file__).parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")
    gm_source = source[source.index("function gmPayBreakdown"):source.index("async function init")]
    assert "ranking" not in gm_source.lower() and "gm score" not in gm_source.lower() and "empleado del mes" not in gm_source.lower()


def demo_session(session_id, hour, room="SOTANO"):
    return Session(id=session_id, room_id=room, starts_at=datetime(2026, 9, 1, hour), status="completed", customers=1)


@pytest.mark.parametrize(("sessions", "expected"), [
    ([demo_session("A", 17), demo_session("B", 20)], set()),
    ([demo_session("A", 17), demo_session("B", 17)], set()),
    ([demo_session("A", 17), demo_session("B", 18)], {"A", "B"}),
    ([demo_session("A", 17), demo_session("B", 18), demo_session("C", 19), demo_session("D", 20)], {"A", "B", "C", "D"}),
    ([demo_session("A", 10), demo_session("B", 11), demo_session("C", 18), demo_session("D", 19)], {"A", "B", "C", "D"}),
    ([demo_session("A", 17), demo_session("B", 18), demo_session("C", 22)], {"A", "B"}),
])
def test_symmetric_connected_overlap_cases(sessions, expected):
    evidence = infer_double_evidence("SOTANO", sessions)
    assert set(evidence) == expected
    for session_id, links in evidence.items():
        assert links and all(link["session_id"] in expected for link in links)


def test_proximity_never_applies_to_other_room_or_cross_room():
    hammer = [demo_session("H1", 17, "HAMMER"), demo_session("H2", 18, "HAMMER")]
    assert infer_double_evidence("HAMMER", hammer) == {}
    sotano = [demo_session("S", 17)]
    assert infer_double_evidence("SOTANO", sotano + hammer) == {}


def test_cross_gm_overlap_is_symmetric_and_activity_is_unchanged(db):
    setup_dimensions(db)
    db.add(GameMaster(id="GM-ABEL", display_name="Bruma", home_location_id="LA_FLORIDA"))
    db.add_all([
        Session(id="JA", room_id="SOTANO", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 1, 17), status="completed", customers=4, revenue=100),
        Session(id="AB", room_id="SOTANO", game_master_id="GM-ABEL", starts_at=datetime(2026, 9, 1, 18), status="completed", customers=6, revenue=150),
    ])
    db.commit()
    javi = gm_summary(db, "GM-JAVI", date(2026, 9, 1), date(2026, 9, 30))
    abel = gm_summary(db, "GM-ABEL", date(2026, 9, 1), date(2026, 9, 30))
    assert (javi["sessions"], javi["normal"], javi["double"], javi["players"], javi["estimated_pay"]) == (1, 0, 1, 4, 26)
    assert (abel["sessions"], abel["normal"], abel["double"], abel["players"], abel["estimated_pay"]) == (1, 0, 1, 6, 26)
    assert javi["details"][0]["overlap_evidence"][0]["session_id"] == "AB"
    assert abel["details"][0]["overlap_evidence"][0]["session_id"] == "JA"
    assert sum(row["players"] for row in javi["details"]) == 4


def test_isolated_explicit_confirmation_has_priority(db):
    setup_dimensions(db)
    db.add(Session(id="EX", room_id="SOTANO", game_master_id="GM-JAVI", starts_at=datetime(2026, 9, 1, 10), status="completed", customers=5, requires_double_gm=True, double_gm_source="EXPLICIT"))
    db.commit()
    row = gm_summary(db, "GM-JAVI", date(2026, 9, 1), date(2026, 9, 30))["details"][0]
    assert row["session_type"] == "double" and row["double_status"] == "confirmed" and row["overlap_evidence"] == []


@pytest.mark.parametrize("fragment", [
    "Cómo se determinó", "Las dos sesiones implicadas se consideran dobles",
    "cadena continua de solapamientos", "No evalúa su rendimiento laboral",
])
def test_v261_explainability_copy(fragment):
    source = (Path(__file__).parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")
    assert fragment in source
