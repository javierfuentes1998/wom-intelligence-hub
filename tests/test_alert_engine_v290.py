import json
from datetime import date,datetime,timedelta
from app.alerts import DETECTORS,engine_status,evaluate_alerts
from app.models import Alert,Location,Room,Session

def setup_room(db):
    db.add(Location(id='L',name='Local'));db.add(Room(id='R',location_id='L',name='Sala',capacity=8));db.commit()
def add_period(db,prefix,start,count,revenue,status='completed'):
    for i in range(count):db.add(Session(id=f'{prefix}{i}',room_id='R',starts_at=datetime.combine(start+timedelta(days=i%20),datetime.min.time()),status=status,customers=4,revenue=revenue,available=True))
    db.commit()
def test_five_gates_reject_small_sample(db):
    setup_room(db);today=date.today();add_period(db,'b',today-timedelta(days=50),2,100);add_period(db,'c',today-timedelta(days=20),1,50)
    evaluate_alerts(db,today);assert db.query(Alert).count()==0
def test_negative_and_positive_semantics(db):
    setup_room(db);today=date.today();add_period(db,'b',today-timedelta(days=50),20,100);add_period(db,'c',today-timedelta(days=20),20,30)
    evaluate_alerts(db,today);row=db.query(Alert).filter(Alert.alert_key=='room:R:revenue').one();assert json.loads(row.evidence)['event_type']=='REQUIERE ATENCIÓN'
    for x in db.query(Session).filter(Session.id.like('c%')):x.revenue=160
    db.commit();evaluate_alerts(db,today);assert json.loads(row.evidence)['event_type']=='EVOLUCIÓN POSITIVA' and row.severity=='positiva'
def test_duplicate_update_resolution_and_reappearance(db):
    setup_room(db);today=date.today();add_period(db,'b',today-timedelta(days=50),20,100);add_period(db,'c',today-timedelta(days=20),20,30)
    evaluate_alerts(db,today);evaluate_alerts(db,today);assert db.query(Alert).count()==1
    for x in db.query(Session).filter(Session.id.like('c%')):x.revenue=100
    db.commit();evaluate_alerts(db,today);assert db.query(Alert).one().status=='RESOLVED'
    for x in db.query(Session).filter(Session.id.like('c%')):x.revenue=30
    db.commit();evaluate_alerts(db,today);assert db.query(Alert).count()==2 and db.query(Alert).filter(Alert.status=='ACTIVE').count()==1
def test_engine_status_and_contracts(db):
    setup_room(db);status=engine_status(db);assert status['timezone']=='Europe/Madrid' and status['next_daily_summary'].hour==9
    assert all({'source_module','metric','min_sample','threshold'}<=set(x) for x in DETECTORS.values())
