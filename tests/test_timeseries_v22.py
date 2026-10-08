from datetime import date,datetime,timedelta
from pathlib import Path
from app.models import Expense,ExpenseCategory,Location,Room,Session
from app.service import kpis
from app.timeseries import business_timeseries,choose_granularity,METRICS

def setup(db):
    db.add_all([Location(id="L1",name="Local 1"),Location(id="L2",name="Local 2"),Room(id="R1",location_id="L1",name="Sala 1",capacity=8),Room(id="R2",location_id="L2",name="Sala 2",capacity=8),ExpenseCategory(id=1,name="otros")]);db.flush()
    base=date(2026,1,1)
    for i in range(10):
        db.add(Session(id=f"A{i}",room_id="R1",starts_at=datetime.combine(base+timedelta(days=i),datetime.min.time()),status="completed",customers=4,revenue=100,available=True))
        db.add(Session(id=f"B{i}",room_id="R2",starts_at=datetime.combine(base+timedelta(days=i),datetime.min.time()),status="cancelled" if i<2 else "completed",customers=0 if i<2 else 2,revenue=0 if i<2 else 50,available=True))
    db.add(Expense(id="E1",concept="Gasto",category_id=1,amount=200,expense_date=base,location_id="L1",room_id="R1"));db.commit();return base

def test_granularity_rules():
    d=date(2026,1,1);assert choose_granularity(d,d)=="day";assert choose_granularity(d,d+timedelta(days=6))=="day";assert choose_granularity(d,d+timedelta(days=29))=="day";assert choose_granularity(d,d+timedelta(days=89))=="month";assert choose_granularity(d,d+timedelta(days=364))=="month";assert choose_granularity(d,d+timedelta(days=800))=="quarter"

def test_multimetric_units_and_aggregation(db):
    d=setup(db);metrics=["revenue","expenses","profit","reservations","sessions","customers","cancellations","margin","average_ticket","occupancy"];x=business_timeseries(db,d,d+timedelta(days=9),metrics)
    assert x["totals"]["revenue"]==1400 and x["totals"]["expenses"]==200 and x["totals"]["profit"]==1200
    assert sum(p["values"]["revenue"] for p in x["series"])==x["totals"]["revenue"]
    assert x["totals"]["reservations"]==18 and x["totals"]["sessions"]==20 and x["totals"]["customers"]==56 and x["totals"]["cancellations"]==2
    assert round(x["totals"]["margin"],2)==85.71 and x["totals"]["average_ticket"]==25 and x["totals"]["occupancy"]==90
    assert {m["unit"] for m in x["metrics"]}=={"EUR","count","percent"}
    executive=kpis(db,d,d+timedelta(days=9))["kpis"]
    for key in ("revenue","expenses","profit","margin","reservations","customers","average_ticket","occupancy"):
        assert x["totals"][key]==executive[key]["value"]

def test_company_location_room_and_empty(client,db):
    d=setup(db);url=f"/api/analytics/timeseries?start_date={d}&end_date={d+timedelta(days=9)}&metrics=revenue&metrics=reservations"
    company=client.get(url).json();local=client.get(url+"&scope_type=location&scope_id=L1").json();room=client.get(url+"&scope_type=room&scope_id=R2").json()
    assert company["totals"]["revenue"]>local["totals"]["revenue"]>room["totals"]["revenue"]
    empty=client.get("/api/analytics/timeseries?start_date=2035-01-01&end_date=2035-01-07&metrics=revenue").json();assert empty["empty"] and empty["series"]==[]
    assert client.get("/api/analytics/timeseries?start_date=2026-02-01&end_date=2026-01-01").status_code==422
    for granularity in ("day","week","month","quarter"):
        response=client.get(url+f"&granularity={granularity}")
        assert response.status_code==200 and response.json()["granularity"]==granularity

def test_accrued_monthly_expense_preserves_total_and_point_expense(db):
    d=setup(db)
    db.add(Expense(id="E2",concept="Alquiler mensual",category_id=1,amount=310,expense_date=d,location_id="L1",room_id="R1",recurring=True,periodicity="monthly",recurrence_key="rent:2026-01"));db.commit()
    accounting=business_timeseries(db,d,d+timedelta(days=9),["expenses"],expense_view="accounting")
    accrued=business_timeseries(db,d,d+timedelta(days=30),["expenses"],expense_view="accrued")
    assert accounting["series"][0]["values"]["expenses"]==510
    assert accrued["totals"]["expenses"]==510
    assert round(sum(p["values"]["expenses"] for p in accrued["series"]),2)==510
    assert db.get(Expense,"E2").amount==310 and db.get(Expense,"E2").expense_date==d

def test_metric_palette_contract():
    assert len(METRICS)==13;assert len({x[2] for x in METRICS.values()})==len(METRICS)
    root=Path(__file__).parents[1]/"frontend";css=(root/"v22.css").read_text(encoding="utf-8")+(root/"v22-extra.css").read_text(encoding="utf-8")
    for _,_,token in METRICS.values():assert f"--{token}:" in css
    for token in ("--semantic-positive:","--semantic-negative:","--brand-accent:","--categorical-1:"):assert token in css
