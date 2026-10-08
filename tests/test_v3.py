from datetime import date,datetime,timedelta
from app.alerts import evaluate_alerts,relevance
from app.chat import answer
import json
from app.models import Alert,DataSource,Expense,ExpenseCategory,GameMaster,GameMasterRate,Location,Review,Room,Session
from app.sync import sync_source

def dims(db):
    db.add(Location(id="L",name="Local V3"));db.add(Room(id="R",location_id="L",name="Sala V3",capacity=8));db.add(DataSource(id="book",name="Booking",source_type="test",status="NEW"));db.commit()

def test_relevance_explains_sample_size():
    weak=relevance(20,2)[1];strong=relevance(20,30)[1];assert strong>weak

def test_alert_lifecycle_deduplicates_and_resolves(db):
    dims(db);today=date.today()
    for i in range(20):
        db.add(Session(id=f"old{i}",room_id="R",starts_at=datetime.combine(today-timedelta(days=52-i),datetime.min.time()),status="completed",customers=4,revenue=100,available=True))
        db.add(Session(id=f"new{i}",room_id="R",starts_at=datetime.combine(today-timedelta(days=25-i),datetime.min.time()),status="completed",customers=4,revenue=30,available=True))
    db.commit();evaluate_alerts(db,today);evaluate_alerts(db,today);rows=db.query(Alert).all();assert len([x for x in rows if x.alert_key=="room:R:revenue"])==1;assert any(x.status=="ACTIVE" for x in rows)
    for row in db.query(Session).filter(Session.id.like("new%")):row.revenue=100
    db.commit();evaluate_alerts(db,today);alert=db.query(Alert).filter_by(alert_key="room:R:revenue").one();assert alert.status=="RESOLVED" and alert.resolved_at is not None

def test_alert_severity_changes_with_signal(db):
    dims(db);today=date.today()
    for i in range(8):
        db.add(Session(id=f"b{i}",room_id="R",starts_at=datetime.combine(today-timedelta(days=50-i),datetime.min.time()),status="completed",customers=4,revenue=100,available=True));db.add(Session(id=f"c{i}",room_id="R",starts_at=datetime.combine(today-timedelta(days=20-i),datetime.min.time()),status="completed",customers=4,revenue=81,available=True))
    db.commit();evaluate_alerts(db,today);row=db.query(Alert).filter_by(alert_key="room:R:revenue").one();assert row.severity=="atención"
    for session in db.query(Session).filter(Session.id.like("c%")):session.revenue=30
    db.commit();evaluate_alerts(db,today);assert db.query(Alert).filter_by(alert_key="room:R:revenue").one().severity=="crítica"

def test_sync_create_update_and_idempotence(db):
    dims(db);db.add(GameMaster(id="GM1",display_name="GM 1"));db.add(GameMaster(id="GM2",display_name="GM 2"));db.commit();row={"external_id":"100","room_id":"R","starts_at":"2026-09-01T18:00:00","customers":4,"revenue":80,"game_master_id":"GM1"}
    first=sync_source(db,"book",[row]);assert first["created"]==1
    row.update(revenue=105,status="cancelled",game_master_id="GM2");second=sync_source(db,"book",[row]);saved=db.get(Session,"book:100");assert second["updated"]==1 and second["alerts_recalculated"];assert saved.revenue==105 and saved.status=="cancelled" and saved.game_master_id=="GM2";third=sync_source(db,"book",[row]);assert third["created"]==0 and db.query(Session).count()==1

def test_assistant_context_and_session(db):
    dims(db);r=answer(db,"Compara los locales",{"start":"2026-09-01","end":"2026-09-30"},"conv",False);assert r["session_id"]=="conv" and r["tool"]=="locations"
    follow=answer(db,"¿Y el periodo anterior?",{"start":"2026-09-01","end":"2026-09-30"},"conv",False);assert follow["tool"]=="locations"

def test_assistant_safe_tool_catalog(db):
    dims(db);today=date.today();db.add(ExpenseCategory(id=1,name="alquiler"));db.add(GameMaster(id="GM-DEMO-03",display_name="GM DEMO 03"));db.add(GameMasterRate(location_id="L",amount=20,rate_type="normal",valid_from=today-timedelta(days=30)));db.add(Session(id="S",room_id="R",game_master_id="GM-DEMO-03",starts_at=datetime.now(),status="completed",customers=4,revenue=100,available=True));db.add(Expense(id="E",concept="Alquiler",category_id=1,amount=50,expense_date=today,location_id="L"));db.add(Review(id="V",review_date=today,source="DEMO",location_id="L",room_id="R",rating=2,original_text="calor",processed_text="calor",sentiment="negativo",sentiment_score=-1,topics=json.dumps([{"aspect":"temperatura","sentiment":"negativo"}])));db.commit()
    ctx={"start":str(today-timedelta(days=2)),"end":str(today+timedelta(days=2))}
    cases=[("reservas","reservations"),("gastos de alquiler","expenses"),("salas","rooms"),("GM DEMO 03","game_masters"),("cancelaciones","cancellations"),("problemas en reseñas","reviews"),("previsión próxima","forecast")]
    for question,tool in cases:assert answer(db,question,ctx,"catalog",False)["tool"]==tool
