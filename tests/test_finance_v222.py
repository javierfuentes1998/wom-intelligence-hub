from datetime import date,datetime
from app.chat import answer
from app.demo_gm import DEMO_GAME_MASTERS,ensure_v223_rates,migrate_demo_game_masters
from app.finance import finance_center
from app.gm import gm_summary
from app.models import Expense,ExpenseCategory,GameMaster,Location,Room,Session

def dimensions(db):
    db.add_all([Location(id="LA_FLORIDA",name="Florida"),Location(id="ALTOZANO",name="Altozano"),Location(id="LOS_ANGELES",name="Los Ángeles"),Location(id="ORIHUELA",name="Orihuela")]);db.flush()
    db.add_all([Room(id="SOTANO",location_id="LA_FLORIDA",name="El Sótano",capacity=8),Room(id="YUCATAN",location_id="ALTOZANO",name="Yucatán",capacity=6),Room(id="SEMILLAS",location_id="LOS_ANGELES",name="Semillas",capacity=6),Room(id="PESADILLAS",location_id="ORIHUELA",name="Pesadillas",capacity=8),ExpenseCategory(id=1,name="alquiler"),ExpenseCategory(id=2,name="reparaciones")]);db.commit()

def test_finance_summary_breakdown_and_scope(db):
    dimensions(db);d=date(2026,9,1)
    db.add_all([Session(id="S1",room_id="SOTANO",starts_at=datetime(2026,9,2,18),status="completed",customers=4,revenue=100,available=True),Session(id="S2",room_id="YUCATAN",starts_at=datetime(2026,9,2,18),status="completed",customers=3,revenue=60,available=True),Expense(id="E1",concept="Alquiler",category_id=1,amount=50,expense_date=d,location_id="LA_FLORIDA",recurring=True,periodicity="monthly"),Expense(id="E2",concept="Reparación",category_id=2,amount=10,expense_date=d,location_id="ALTOZANO")]);db.commit()
    x=finance_center(db,d,date(2026,9,30));k=x["summary"]["kpis"]
    assert (k["revenue"]["value"],k["expenses"]["value"],k["profit"]["value"],k["margin"]["value"])==(160,60,100,62.5)
    assert sum(row["amount"] for row in x["expense_breakdown"])==60
    assert x["expense_mix"]["recurring"]+x["expense_mix"]["one_off"]==60
    assert sum(row["expenses"] for row in x["locations"])==60 and x["unassigned_costs"]==0
    assert all(row["direct_costs"] is None and row["contribution"] is None for row in x["rooms"])

def test_finance_unassigned_and_direct_cost_are_not_invented(db):
    dimensions(db);d=date(2026,9,1)
    db.add_all([Expense(id="GLOBAL",concept="Corporativo",category_id=1,amount=80,expense_date=d),Expense(id="DIRECT",concept="Directo",category_id=2,amount=20,expense_date=d,location_id="ALTOZANO",room_id="YUCATAN")]);db.commit()
    x=finance_center(db,d,d);room=next(r for r in x["rooms"] if r["id"]=="YUCATAN")
    assert x["unassigned_costs"]==80 and room["direct_costs"]==20 and room["contribution"]==-20

def test_demo_gm_migration_is_reproducible_and_preserves_business(db):
    dimensions(db)
    for i in range(1,13):db.add(GameMaster(id=f"GM-DEMO-{i:02}",display_name=f"GM {i}"))
    db.flush();db.add(Session(id="S",room_id="SOTANO",game_master_id="GM-DEMO-01",second_game_master_id="GM-DEMO-02",starts_at=datetime(2026,9,1,18),status="completed",customers=6,revenue=120,available=True,requires_double_gm=True));db.commit()
    before=(db.query(Session).count(),sum(s.revenue for s in db.query(Session)),sum(s.customers for s in db.query(Session)))
    assert migrate_demo_game_masters(db)
    names={(g.display_name,g.home_location_id) for g in db.query(GameMaster)}
    assert names=={(name,location) for _,name,location in DEMO_GAME_MASTERS}
    assert not any(g.id.startswith("GM-DEMO") for g in db.query(GameMaster))
    saved=db.get(Session,"S");assert saved.game_master_id!=saved.second_game_master_id
    assert before==(db.query(Session).count(),sum(s.revenue for s in db.query(Session)),sum(s.customers for s in db.query(Session)))

def test_confirmed_los_angeles_rate_is_applied(db):
    dimensions(db);db.add(GameMaster(id="GM-JAVI-ESPIN",display_name="Lumera",home_location_id="LOS_ANGELES"));db.add(Session(id="S",room_id="SEMILLAS",game_master_id="GM-JAVI-ESPIN",starts_at=datetime(2026,9,1,18),status="completed",customers=4,revenue=100));db.commit()
    assert ensure_v223_rates(db)
    x=gm_summary(db,"GM-JAVI-ESPIN",date(2026,9,1),date(2026,9,2))
    assert x["estimated_pay"]==20 and x["pay_complete"] and x["missing_rate_sessions"]==0

def test_chat_resolves_javi_and_javi_espin_exactly(db):
    dimensions(db);db.add_all([GameMaster(id="GM-JAVI",display_name="Aster",home_location_id="LA_FLORIDA"),GameMaster(id="GM-JAVI-ESPIN",display_name="Lumera",home_location_id="LOS_ANGELES")]);db.commit();ctx={"start":"2026-09-01","end":"2026-09-30"}
    assert answer(db,"¿Qué datos tienes de Aster?",ctx,"j1",False)["data"]["game_master"]=="Aster"
    assert answer(db,"¿Qué datos tienes de Lumera?",ctx,"j2",False)["data"]["game_master"]=="Lumera"

def test_chat_answers_financial_profit_from_backend(db):
    dimensions(db);d=date(2026,9,1)
    db.add(Session(id="S",room_id="SOTANO",starts_at=datetime(2026,9,2,18),status="completed",customers=4,revenue=100,available=True))
    db.add(Expense(id="E",concept="Alquiler",category_id=1,amount=40,expense_date=d,location_id="LA_FLORIDA"));db.commit()
    result=answer(db,"¿Cuál es el beneficio del periodo?",{"start":"2026-09-01","end":"2026-09-30"},"finance",False)
    assert result["tool"]=="finance" and result["data"]["profit"]==60 and result["data"]["margin"]==60

def test_payroll_and_gm_rate_are_independent_and_chat_distinguishes_them(db):
    dimensions(db);ensure_v223_rates(db);d=date(2026,9,1)
    db.add(GameMaster(id="GM-JAVI-ESPIN",display_name="Lumera",home_location_id="LOS_ANGELES"))
    db.add(Expense(id="PAYROLL",concept="Nóminas LOS_ANGELES",category_id=1,amount=5900,expense_date=d,location_id="LOS_ANGELES",recurring=True,periodicity="monthly"));db.commit()
    ctx={"start":"2026-09-01","end":"2026-09-30"}
    rate=answer(db,"¿Cuánto cobra Lumera por sesión?",ctx,"rate",False)
    payroll=answer(db,"¿Cuánto gastamos en nóminas en Los Ángeles?",ctx,"payroll",False)
    assert rate["data"]["rate"]==20 and payroll["data"]["value"]==5900
    assert db.get(Expense,"PAYROLL").amount==5900

def test_periodified_daily_coverage_positive_negative_and_zero(db):
    dimensions(db);d=date(2026,9,1)
    db.add_all([Session(id="P",room_id="SOTANO",starts_at=datetime(2026,9,1,18),status="completed",customers=2,revenue=20,available=True),Session(id="Z",room_id="SOTANO",starts_at=datetime(2026,9,2,18),status="completed",customers=2,revenue=10,available=True),Expense(id="MONTHLY",concept="Mensual",category_id=1,amount=300,expense_date=d,location_id="LA_FLORIDA",recurring=True,periodicity="monthly")]);db.commit()
    x=finance_center(db,d,date(2026,9,30),expense_view="accrued");days={row["date"]:row for row in x["daily_cost_coverage"]["days"]}
    assert days["2026-09-01"]["result"]==10 and days["2026-09-01"]["costs_covered"]
    assert days["2026-09-02"]["result"]==0 and days["2026-09-02"]["costs_covered"]
    assert days["2026-09-03"]["result"]==-10 and not days["2026-09-03"]["costs_covered"]
