from datetime import date,datetime
from app.db import Base
from app.gm import infer_double,rate_for,gm_summary
from app.models import GameMaster,GameMasterRate,Location,Room,Session

def dims(db):
    db.add_all([Location(id="LA_FLORIDA",name="Florida"),Location(id="ALTOZANO",name="Altozano"),Location(id="ORIHUELA",name="Orihuela")]);db.flush();db.add_all([Room(id="SOTANO",location_id="LA_FLORIDA",name="El Sótano",capacity=8),Room(id="OTHER",location_id="ALTOZANO",name="Otra",capacity=8),GameMaster(id="G1",display_name="DEMO 1"),GameMaster(id="G2",display_name="DEMO 2")]);db.flush()
    for loc,amt in [("LA_FLORIDA",20),("ALTOZANO",18),("LOS_ANGELES",20),("ORIHUELA",25)]:db.add(GameMasterRate(location_id=loc,amount=amt,rate_type="normal",valid_from=date(2020,1,1)))
    db.add(GameMasterRate(location_id="LA_FLORIDA",room_id="SOTANO",amount=26,rate_type="double",valid_from=date(2020,1,1)));db.commit()
def test_known_rates(db):
    dims(db);assert rate_for(db,"LA_FLORIDA",date.today())==20;assert rate_for(db,"ALTOZANO",date.today())==18;assert rate_for(db,"LOS_ANGELES",date.today())==20;assert rate_for(db,"ORIHUELA",date.today())==25
def test_historical_rate(db):
    dims(db);db.add(GameMasterRate(location_id="ALTOZANO",amount=20,rate_type="normal",valid_from=date(2027,1,1)));db.commit();assert rate_for(db,"ALTOZANO",date(2026,1,1))==18;assert rate_for(db,"ALTOZANO",date(2027,2,1))==20
def test_sotano_normal_two_hours(): assert infer_double("SOTANO",[datetime(2026,1,1,18),datetime(2026,1,1,20)])==set()
def test_sotano_hourly_is_double(): assert len(infer_double("SOTANO",[datetime(2026,1,1,18),datetime(2026,1,1,19)]))==2
def test_other_room_never_inferred(): assert infer_double("OTHER",[datetime(2026,1,1,18),datetime(2026,1,1,19)])==set()
def test_double_two_gms_paid_each(db):
    dims(db);s=Session(id="S",room_id="SOTANO",game_master_id="G1",second_game_master_id="G2",starts_at=datetime(2026,1,2,18),status="completed",customers=6,revenue=120,requires_double_gm=True,double_gm_source="CONFIRMED");db.add(s);db.commit();assert gm_summary(db,"G1",date(2026,1,1),date(2026,1,3))["estimated_pay"]==26;assert gm_summary(db,"G2",date(2026,1,1),date(2026,1,3))["estimated_pay"]==26
def test_inactive_gm_keeps_history(db):
    dims(db);g=db.get(GameMaster,"G1");g.active=False;db.add(Session(id="S",room_id="OTHER",game_master_id="G1",starts_at=datetime(2026,1,2,18),status="completed",customers=4,revenue=80));db.commit();assert gm_summary(db,"G1",date(2026,1,1),date(2026,1,3))["sessions"]==1
