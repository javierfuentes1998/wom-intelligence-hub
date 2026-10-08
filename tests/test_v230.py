import json
from datetime import date, datetime, timedelta

from app.models import Alert, Expense, ExpenseCategory, GameMaster, Location, Room, Session
from app.chat import answer


ROOMS={
    "LA_FLORIDA":[("SOTANO","El Sótano"),("HAMMER","Hammer Killer"),("JUDY","Las Reliquias de Judy")],
    "ALTOZANO":[("YUCATAN","Yucatán"),("MAGIA","Escuela de Magia"),("BASILISCO","El Veneno del Basilisco")],
    "LOS_ANGELES":[("SEMILLAS","Las Semillas de la Locura")],
    "ORIHUELA":[("PESADILLAS","Pesadillas II")],
}


def seed_scope(db):
    for location_id in ROOMS:
        db.add(Location(id=location_id,name=location_id))
    for location_id, rooms in ROOMS.items():
        for room_id,name in rooms:
            db.add(Room(id=room_id,location_id=location_id,name=name,capacity=8))
    db.add(ExpenseCategory(id=1,name="nóminas"));db.add(GameMaster(id="GM-JAVI",display_name="Lumera",home_location_id="LOS_ANGELES"));db.commit()


def test_location_room_structure_and_kpi_isolation(client,db):
    seed_scope(db);start=datetime(2026,9,1,18)
    for i,(location_id,rooms) in enumerate(ROOMS.items()):
        db.add(Session(id=f"S{i}",room_id=rooms[0][0],starts_at=start,status="completed",customers=i+1,revenue=100*(i+1),available=True))
    db.commit()
    all_rooms=client.get("/api/rooms?start=2026-09-01&end=2026-09-30").json()
    assert {key:sum(r["location_id"]==key for r in all_rooms) for key in ROOMS}=={"LA_FLORIDA":3,"ALTOZANO":3,"LOS_ANGELES":1,"ORIHUELA":1}
    assert len(all_rooms)==8
    for i,location_id in enumerate(ROOMS):
        k=client.get(f"/api/dashboard?start=2026-09-01&end=2026-09-30&location_id={location_id}").json()["kpis"]
        assert k["revenue"]["value"]==100*(i+1) and k["reservations"]["value"]==1 and k["customers"]["value"]==i+1


def test_alerts_are_isolated_by_location(client,db):
    seed_scope(db)
    for room_id in ("YUCATAN","PESADILLAS"):
        db.add(Alert(id=room_id,category="Reservas",severity="crítica",title=room_id,explanation="x",evidence=json.dumps({"room_id":room_id,"sample_size":10}),status="ACTIVE"))
    db.commit()
    florida=client.get("/api/alerts?status=ACTIVE&location_id=LA_FLORIDA").json();angeles=client.get("/api/alerts?status=ACTIVE&location_id=LOS_ANGELES").json()
    assert florida==[] and angeles==[]
    assert [x["title"] for x in client.get("/api/alerts?status=ACTIVE&location_id=ALTOZANO").json()]==["YUCATAN"]


def test_income_search_sort_filter_and_pagination_cover_full_dataset(client,db):
    seed_scope(db);base=datetime(2026,9,1,10)
    for i in range(260):
        db.add(Session(id=f"I{i:03}",room_id="SEMILLAS" if i==259 else "SOTANO",game_master_id="GM-JAVI" if i==259 else None,starts_at=base+timedelta(minutes=i),status="cancelled" if i==259 else "completed",customers=i%8,revenue=float(i),payment_method="card",available=True))
    db.commit();url="/api/finance/income-detail?start=2026-09-01&end=2026-09-30&page_size=25"
    first=client.get(url+"&sort=revenue&direction=asc").json();second=client.get(url+"&sort=revenue&direction=asc&page=2").json()
    assert first["total"]==260 and first["items"][0]["revenue"]==0 and second["items"][0]["revenue"]==25
    found=client.get(url+"&search=Lumera").json();assert found["filtered_total"]==1 and found["items"][0]["id"]=="I259"
    combined=client.get(url+"&filter_location=LOS_ANGELES&filter_room=SEMILLAS&gm=Lumera&status=cancelled&payment=card&revenue_min=250").json();assert combined["filtered_total"]==1


def test_expense_filters_sort_and_validation(client,db):
    seed_scope(db);d=date(2026,9,1)
    db.add_all([Expense(id="E1",concept="Nóminas Los Ángeles",category_id=1,amount=5900,expense_date=d,location_id="LOS_ANGELES",recurring=True,periodicity="monthly"),Expense(id="E2",concept="Nóminas Florida",category_id=1,amount=5200,expense_date=d,location_id="LA_FLORIDA")]);db.commit()
    url="/api/finance/expense-detail?start=2026-09-01&end=2026-09-30&page_size=25"
    result=client.get(url+"&search=los%20%C3%A1ngeles&category=n%C3%B3minas&filter_location=LOS_ANGELES&expense_type=Recurrente&amount_min=5000&sort=amount&direction=desc").json()
    assert result["filtered_total"]==1 and result["items"][0]["amount"]==5900
    assert client.get(url+"&sort=drop_table").status_code==422
    assert client.get(url+"&amount_min=10&amount_max=1").status_code==422
    assert client.get(url+"&page=0").status_code==422


def test_chat_distinguishes_local_and_company_room_counts(db):
    seed_scope(db)
    florida=answer(db,"¿Cuántas salas tiene La Florida?",{},"rooms",False)
    company=answer(db,"¿Cuántas salas tiene WOM?",{},"company-rooms",False)
    assert florida["data"]["count"]==3 and florida["data"]["rooms"]==["El Sótano","Hammer Killer","Las Reliquias de Judy"]
    assert company["data"]["count"]==8
