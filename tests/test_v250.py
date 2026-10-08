from datetime import datetime
from pathlib import Path

from app.models import Session
from app.demand_map import _level, _reference_assignment
from app.room_detail import _health
from app.schedules import REFERENCE_SCHEDULES
from tests.test_v240 import seed


EXPECTED={
    "YUCATAN":["10:30","12:30","14:30","16:30","18:30","20:30","22:30"],
    "MAGIA":["10:00","12:00","14:00","16:00","18:00","20:00","22:00"],
    "HAMMER":["09:15","11:45","14:45","17:15","19:45","22:15"],
    "SEMILLAS":["09:30","11:30","13:30","16:00","18:00","20:00","22:00"],
    "RELIQUIAS":["10:30","12:30","14:30","16:30","18:30","20:30","22:30"],
    "SOTANO":["09:30","10:30","11:30","12:30","13:30","14:30","16:00","17:00","18:00","19:00","20:00","21:00","22:00"],
    "PESADILLAS_II":["10:00","12:30","16:00","18:30","21:00"],
    "BASILISCO":["09:30","12:00","17:15","18:30","20:45"],
}


def test_exact_reference_schedules():
    assert REFERENCE_SCHEDULES==EXPECTED
    assert {room:len(hours) for room,hours in REFERENCE_SCHEDULES.items()}=={"YUCATAN":7,"MAGIA":7,"HAMMER":6,"SEMILLAS":7,"RELIQUIAS":7,"SOTANO":13,"PESADILLAS_II":5,"BASILISCO":5}


def test_official_schedules_do_not_invent_nearby_slots():
    assert "09:15" in REFERENCE_SCHEDULES["HAMMER"] and "09:30" not in REFERENCE_SCHEDULES["HAMMER"]
    assert "11:45" in REFERENCE_SCHEDULES["HAMMER"] and "12:00" not in REFERENCE_SCHEDULES["HAMMER"]
    assert "10:30" in REFERENCE_SCHEDULES["YUCATAN"] and "11:30" not in REFERENCE_SCHEDULES["YUCATAN"]
    assert "17:15" in REFERENCE_SCHEDULES["BASILISCO"] and "17:00" not in REFERENCE_SCHEDULES["BASILISCO"]
    assert "20:45" in REFERENCE_SCHEDULES["BASILISCO"] and "21:00" not in REFERENCE_SCHEDULES["BASILISCO"]
    assert not ({"15:00","15:30","23:00"} & set(REFERENCE_SCHEDULES["SOTANO"]))


def test_health_missing_dimensions_are_not_zero_and_weights_are_renormalized():
    health=_health(None,50,None)
    assert health["score"]==50
    assert health["complete"] is False
    components={item["key"]:item for item in health["components"]}
    assert components["occupancy"]["effective_weight"]==1
    assert components["revenue_trend"]["normalized"] is None
    assert components["cancellations"]["normalized"] is None
    assert sum(item["effective_weight"] for item in health["components"])==1


def test_demand_categories_are_deterministic_and_distinguish_zero():
    assert _level(0,4)["label"]=="Sin demanda"
    assert _level(1,5)["label"]=="Baja"
    assert _level(1,4)["label"]=="Media"
    assert _level(2,4)["label"]=="Alta"
    assert _level(4,4)["label"]=="Máxima"
    assert _level(0,0)["key"]=="unavailable"


def test_demand_map_room_scope_zero_unavailable_and_reconciliation(client,db):
    seed(db);db.add(Session(id="AVAILABLE",room_id="SOTANO",starts_at=datetime(2026,9,4,20),status="available",customers=0,revenue=0,available=True));db.commit()
    data=client.get("/api/demand/map?start=2026-09-01&end=2026-09-30&room_id=SOTANO").json()
    assert data["hours"]==EXPECTED["SOTANO"] and {x["id"] for x in data["rooms"]}=={"SOTANO"}
    assert len(data["weekly"])==7 and len(data["calendar"])==30
    cells=[x for day in data["calendar"] for x in day["cells"]]
    assert all(x["available"]>0 and x["occupancy"] is not None for x in cells)
    assert any(x["available"]>0 and x["reservations"]==0 and x["occupancy"]==0 for x in cells)
    dashboard=client.get("/api/dashboard?start=2026-09-01&end=2026-09-30&room_id=SOTANO").json()["kpis"]
    assert data["totals"]["revenue"]==dashboard["revenue"]["value"]
    assert data["totals"]["reservations"]==dashboard["reservations"]["value"]
    assert data["totals"]["players"]==dashboard["customers"]["value"]


def test_demand_map_company_location_and_room_hours(client,db):
    seed(db)
    company=client.get("/api/demand/map?start=2026-09-01&end=2026-09-30").json()
    florida=client.get("/api/demand/map?start=2026-09-01&end=2026-09-30&location_id=LA_FLORIDA").json()
    hammer=client.get("/api/demand/map?start=2026-09-01&end=2026-09-30&room_id=HAMMER").json()
    assert len(company["rooms"])==8 and {x["id"] for x in florida["rooms"]}=={"SOTANO","HAMMER","RELIQUIAS"}
    assert hammer["hours"]==EXPECTED["HAMMER"]
    assert company["totals"]["reservations"]>=florida["totals"]["reservations"]>=hammer["totals"]["reservations"]


def test_reference_schedule_is_offer_even_without_demo_rows(client,db):
    seed(db)
    hammer=client.get("/api/demand/map?start=2026-09-01&end=2026-09-30&room_id=HAMMER").json()
    assert len(hammer["hours"])==6
    assert all(cell["available"]>0 for row in hammer["weekly"] for cell in row["cells"])
    assert all(cell["available"]>0 for row in hammer["calendar"] for cell in row["cells"])
    assert any(cell["reservations"]==0 and cell["available"]>0 for row in hammer["calendar"] for cell in row["cells"])
    sotano=client.get("/api/demand/map?start=2026-09-01&end=2026-09-30&room_id=SOTANO").json()
    monday_0930=next(cell for cell in sotano["weekly"][0]["cells"] if cell["hour"]=="09:30")
    assert monday_0930["available"]==4 and monday_0930["occupancy"]==0


def test_company_and_location_only_count_rooms_that_offer_the_hour(client,db):
    seed(db)
    company=client.get("/api/demand/map?start=2026-09-01&end=2026-09-30").json()
    company_1130=next(cell for cell in company["weekly"][0]["cells"] if cell["hour"]=="11:30")
    assert company_1130["rooms"]==["SEMILLAS","SOTANO"] and company_1130["available"]==8
    florida=client.get("/api/demand/map?start=2026-09-01&end=2026-09-30&location_id=LA_FLORIDA").json()
    expected={"09:15":["HAMMER"],"09:30":["SOTANO"],"10:30":["RELIQUIAS","SOTANO"]}
    for hour,rooms in expected.items():
        cell=next(cell for cell in florida["weekly"][0]["cells"] if cell["hour"]==hour)
        assert cell["rooms"]==rooms and cell["available"]==4*len(rooms)


def test_calendar_multisala_denominator_counts_only_official_room_slots(client,db):
    seed(db)
    data=client.get("/api/demand/map?start=2026-09-07&end=2026-09-07").json()
    cells={cell["hour"]:cell for cell in data["calendar"][0]["cells"]}
    assert cells["09:15"]["rooms"]==["HAMMER"] and cells["09:15"]["available"]==1
    assert cells["10:30"]["rooms"]==["RELIQUIAS","SOTANO","YUCATAN"]
    assert cells["10:30"]["available"]==3
    assert cells["11:30"]["rooms"]==["SEMILLAS","SOTANO"] and cells["11:30"]["available"]==2


def test_weekly_denominator_uses_real_weekday_occurrences_and_calendar_is_individual(client,db):
    seed(db)
    hammer=client.get("/api/demand/map?start=2026-09-01&end=2026-09-30&room_id=HAMMER").json()
    assert {row["weekday"]:row["cells"][0]["available"] for row in hammer["weekly"]}=={0:4,1:5,2:5,3:4,4:4,5:4,6:4}
    assert all(cell["available"]==1 for row in hammer["calendar"] for cell in row["cells"])


def test_period_without_reservations_has_offer_zeroes_and_no_null_business_totals(client,db):
    seed(db)
    data=client.get("/api/demand/map?start=2035-02-01&end=2035-02-28&room_id=HAMMER").json()
    assert data["totals"]["reservations"]==data["totals"]["players"]==data["totals"]["revenue"]==0
    assert data["totals"]["available"]==28*6 and data["totals"]["occupancy"]==0
    assert all(cell["demand"]["label"]=="Sin demanda" for row in data["calendar"] for cell in row["cells"])


def test_v250_frontend_contract():
    js=(Path(__file__).parents[1]/"frontend"/"app.js").read_text(encoding="utf-8")
    assert "Voice of Customer atribuible" in js  # retained only in V2.4 source, removed by V2.5 composition
    assert "lower.children[1].remove()" in js
    assert "Estado general de la sala" in js and "data-demand-view" in js and "data-demand-metric" in js
    assert "Tasa de cancelación:" in js and "Variación interanual de ingresos" in js
    assert "${cell.reservations} de ${cell.available}" in js
    assert "Explicar Patrón semanal" in js and "Sesiones ofrecidas:" in js
    assert "Explicar Calendario del periodo" in js and "Reservas de viernes a domingo" in js
    assert "Sin demanda" in js and "Ocupación DEMO:" in js
    assert "¿Qué muestra este mapa?" in js and "¿Cómo interpretar este análisis?" in js
    assert "DEMAND_METRIC_EXPLANATIONS" in js and "demand-metric-explanation" in js
    assert "Esto significa que la sesión" in js and "Agrupa las sesiones de las salas seleccionadas" in js
    metric_contract=js.split("const DEMAND_METRICS=",1)[1].split(";",1)[0]
    assert metric_contract=="{demand:'Demanda',occupancy:'Ocupación DEMO'}"
    assert "Solo se consideran los horarios configurados oficialmente" in js


def test_explainability_standard_is_documented():
    text=(Path(__file__).parents[1]/"docs"/"ux_explainability.md").read_text(encoding="utf-8")
    for phrase in ("Tres niveles de explicación","Dato observado","Interpretación","Acción sugerida","Accesibilidad","Aplicación progresiva"):
        assert phrase in text
