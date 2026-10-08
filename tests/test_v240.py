import json
from datetime import date, datetime
from pathlib import Path

from app.models import Alert, GameMaster, Location, Review, Room, Session


ROOMS={
    "LA_FLORIDA":[("SOTANO","El Sótano"),("HAMMER","Hammer Killer"),("RELIQUIAS","Las Reliquias de Judy")],
    "ALTOZANO":[("YUCATAN","Yucatán"),("MAGIA","Escuela de Magia"),("BASILISCO","El Veneno del Basilisco")],
    "LOS_ANGELES":[("SEMILLAS","Las Semillas de la Locura")],
    "ORIHUELA":[("PESADILLAS_II","Pesadillas II")],
}


def seed(db):
    for location_id,rooms in ROOMS.items():
        db.add(Location(id=location_id,name=location_id))
        for room_id,name in rooms:db.add(Room(id=room_id,location_id=location_id,name=name,capacity=8,experience_type="Escape room"))
    db.add_all([GameMaster(id="JAVI",display_name="Aster",home_location_id="LA_FLORIDA"),GameMaster(id="JAVI-ESPIN",display_name="Lumera",home_location_id="LOS_ANGELES")]);db.flush()
    db.add_all([
        Session(id="A",room_id="SOTANO",game_master_id="JAVI",starts_at=datetime(2026,9,2,18),status="completed",customers=4,revenue=120,available=True),
        Session(id="B",room_id="SOTANO",game_master_id="JAVI",second_game_master_id="JAVI-ESPIN",starts_at=datetime(2026,9,3,19),status="cancelled",customers=0,revenue=0,available=True),
        Session(id="C",room_id="MAGIA",game_master_id="JAVI-ESPIN",starts_at=datetime(2026,9,2,18),status="completed",customers=7,revenue=210,available=True),
    ])
    for index,(room_id,_) in enumerate(x for rooms in ROOMS.values() for x in rooms if x[0] not in {"SOTANO","MAGIA"}):
        db.add(Session(id=f"ROOM-{room_id}",room_id=room_id,starts_at=datetime(2026,9,5,17),status="completed",customers=index+2,revenue=50*(index+1),available=True))
    db.add_all([
        Review(id="R1",review_date=date(2026,9,4),source="DEMO",room_id="SOTANO",location_id="LA_FLORIDA",rating=5,original_text="Gran ambientación",processed_text="gran ambientación",sentiment="positivo",sentiment_score=.9,topics=json.dumps([{"aspect":"ambientacion","sentiment":"positivo"}])),
        Review(id="R2",review_date=date(2026,9,4),source="DEMO",room_id=None,location_id="LA_FLORIDA",rating=1,original_text="Sin sala atribuida",processed_text="sin sala",sentiment="negativo",sentiment_score=-.9,topics="[]"),
    ])
    db.add(Alert(id="AL",category="Ingresos",severity="crítica",title="Ingresos por encima de base",explanation="Oportunidad observada",evidence=json.dumps({"room_id":"SOTANO","metric":"revenue","sample_size":2}),status="ACTIVE",deviation=25,relevance_score=82));db.commit()


def test_room_detail_exact_scope_and_reconciliation(client,db):
    seed(db);url="/api/rooms/SOTANO/detail?start=2026-09-01&end=2026-09-30";data=client.get(url).json();k=data["kpis"]
    assert data["room"]["id"]=="SOTANO" and data["room"]["name"]=="El Sótano"
    assert (k["revenue"],k["reservations"],k["players"],k["available_slots"])==(120,1,4,390)
    assert k["occupancy"]==0.26 and k["average_ticket"]==30 and k["players_per_reservation"]==4
    assert k["cancellations"]==1 and k["cancellation_rate"]==50 and k["revenue_per_available_slot"]==0.31
    dashboard=client.get("/api/dashboard?start=2026-09-01&end=2026-09-30&room_id=SOTANO").json()["kpis"]
    assert dashboard["revenue"]["value"]==k["revenue"] and dashboard["reservations"]["value"]==k["reservations"] and dashboard["customers"]["value"]==k["players"]


def test_room_detail_gms_health_and_signal_semantics(client,db):
    seed(db);data=client.get("/api/rooms/SOTANO/detail?start=2026-09-01&end=2026-09-30").json()
    assert data["voc"]["count"]==0 and data["voc"]["topics"]==[]
    assert {x["name"] for x in data["game_masters"]}=={"Aster","Lumera"}
    assert data["alerts"][0]["tone"]=="opportunity" and data["alerts"][0]["label"]=="Oportunidad"
    assert round(sum(x["effective_weight"] for x in data["health"]["components"]),3)==1
    assert {x["key"] for x in data["health"]["components"]}=={"revenue_trend","occupancy","cancellations"}


def test_all_eight_rooms_resolve_and_new_timeseries_metrics(client,db):
    seed(db)
    for room_id,_ in sum(ROOMS.values(),[]):
        response=client.get(f"/api/rooms/{room_id}/detail?start=2026-09-01&end=2026-09-30")
        assert response.status_code==200 and response.json()["room"]["id"]==room_id
        dashboard=client.get(f"/api/dashboard?start=2026-09-01&end=2026-09-30&room_id={room_id}").json()
        assert response.json()["kpis"]["revenue"]==dashboard["kpis"]["revenue"]["value"]
    assert client.get("/api/rooms/NO_EXISTE/detail?start=2026-09-01&end=2026-09-30").status_code==404
    data=client.get("/api/analytics/timeseries?start_date=2026-09-01&end_date=2026-09-30&scope_type=room&scope_id=SOTANO&metrics=players_per_reservation&metrics=cancellation_rate&metrics=revenue_per_slot").json()
    assert data["totals"]=={"players_per_reservation":4.0,"cancellation_rate":50.0,"revenue_per_slot":0.31}


def test_frontend_keeps_internal_ids_and_rooms_navigation():
    js=(Path(__file__).parents[1]/"frontend"/"app.js").read_text(encoding="utf-8")
    assert "S.page='rooms';render()" in js and "find(x=>x.id===b.dataset.room)" in js
    assert 'api(`/api/rooms/${chosen.id}/detail?' in js
    assert "locName(d.room.location_id)" in js
    assert "version!==S.renderVersion||page!==S.page" in js
