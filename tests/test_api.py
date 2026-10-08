from datetime import date
from app.models import ExpenseCategory, Location, Room

def setup_dims(db):
    db.add(Location(id="L1",name="Local"));db.add(Room(id="R1",location_id="L1",name="Sala",capacity=8));db.add(ExpenseCategory(id=1,name="otros"));db.commit()
def test_health(client): assert client.get('/api/health').json()["status"]=="ok"
def test_empty_dashboard_does_not_crash(client):
    r=client.get('/api/dashboard');assert r.status_code==200;assert r.json()["kpis"]["margin"]["value"] is None
def test_filters_empty(client): assert client.get('/api/demand?location_id=unknown').json()==[]
def test_expense_crud_and_duplicate_recurrence(client,db):
    setup_dims(db); body={"concept":"Alquiler","category_id":1,"amount":100,"expense_date":str(date.today()),"location_id":"L1","recurring":True,"periodicity":"mensual","recurrence_key":"L1-rent-2026-09"}
    r=client.post('/api/expenses',json=body);assert r.status_code==201;eid=r.json()["id"]
    assert client.post('/api/expenses',json=body).status_code==409
    body["amount"]=110;assert client.put(f'/api/expenses/{eid}',json=body).json()["amount"]==110
    assert client.delete(f'/api/expenses/{eid}').status_code==204
def test_room_location_validation(client,db):
    setup_dims(db); body={"concept":"X","category_id":1,"amount":2,"expense_date":str(date.today()),"location_id":"OTHER","room_id":"R1"}
    assert client.post('/api/expenses',json=body).status_code==422
def test_assistant_graceful(client):
    r=client.post('/api/assistant/query',json={"question":"¿Cuánto hemos facturado esta semana?"})
    assert r.status_code==200 and r.json()["tool"]=="get_revenue"
def test_bad_metric_is_rejected(client): assert client.get('/api/forecast?metric=drop').status_code==422
