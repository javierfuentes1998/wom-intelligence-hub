from app.data_management import DATASETS,import_selected,sources
from app.models import DataImportRun,Location,Room,Session
from datetime import datetime

def test_connector_capabilities_and_wom_honesty():
    rows=sources();demo=next(x for x in rows if x['id']=='demo');wom=next(x for x in rows if x['id']=='wom')
    assert set(demo['datasets'])==set(DATASETS) and demo['configured'] is True
    assert wom['configured'] is False and wom['datasets']==[] and 'Pendiente' in wom['status']
def test_partial_demo_import_runs_only_selected(db):
    result=import_selected(db,'demo',['reservations','expenses'])
    assert [x['dataset'] for x in result['datasets']]==['reservations','expenses']
    assert 'Demanda' in result['analyses_updated'] and result['alerts_evaluated'] is True
def test_demo_import_is_idempotent(db):
    db.add(Location(id='L',name='L'));db.add(Room(id='R',location_id='L',name='R',capacity=8));db.add(Session(id='S',room_id='R',starts_at=datetime(2026,1,1),status='completed',customers=4,revenue=100,available=True));db.commit()
    first=import_selected(db,'demo',['reservations']);second=import_selected(db,'demo',['reservations'])
    assert first['datasets'][0]['processed']==second['datasets'][0]['processed']==1
    assert second['datasets'][0]['new']==0 and second['datasets'][0]['unchanged']==1 and db.query(Session).count()==1
    assert db.query(DataImportRun).count()==2
def test_invalid_source_dataset_and_unconfigured_wom(db):
    for source,datasets in [('missing',['reservations']),('demo',['unknown']),('wom',['reservations'])]:
        try:import_selected(db,source,datasets);assert False
        except ValueError:pass
def test_data_management_api(client):
    assert client.get('/api/data-management/sources').status_code==200
    response=client.post('/api/data-management/import',json={'source_id':'demo','datasets':['locations']})
    assert response.status_code==200 and response.json()['datasets'][0]['dataset']=='locations'
    assert client.get('/api/data-management/history').json()
