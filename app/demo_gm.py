import hashlib
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from .models import DataSource,GameMaster,GameMasterRate,Room,Session

DEMO_GAME_MASTERS=(
    ("GM-OMAR","Ivarn","ALTOZANO"),("GM-VERO","Hestiax","ALTOZANO"),
    ("GM-JAVI","Aster","LA_FLORIDA"),("GM-ABEL","Bruma","LA_FLORIDA"),("GM-DANI","Cirox","LA_FLORIDA"),("GM-ADRI","Daliax","LA_FLORIDA"),("GM-YERAY","Elar","LA_FLORIDA"),
    ("GM-NANA","Fionex","ORIHUELA"),("GM-PACARDO","Galoz","ORIHUELA"),
    ("GM-JAVI-ESPIN","Lumera","LOS_ANGELES"),
)

def ensure_v223_rates(db:DB):
    exists=db.scalar(select(GameMasterRate).where(GameMasterRate.location_id=="LOS_ANGELES",GameMasterRate.rate_type=="normal",GameMasterRate.valid_to==None))
    if exists:return False
    db.add(GameMasterRate(location_id="LOS_ANGELES",amount=20,rate_type="normal",valid_from=date(2020,1,1),notes="Tarifa confirmada · coste GM por sesión, independiente de nómina contable"));db.commit();return True

def _pick(options,seed,offset=0):
    value=int(hashlib.sha256(f"{seed}:{offset}".encode()).hexdigest()[:12],16)
    return options[value%len(options)]

def migrate_demo_game_masters(db:DB):
    old=db.scalars(select(GameMaster).where(GameMaster.id.like("GM-DEMO-%"))).all()
    if not old:return False
    for gm_id,name,location_id in DEMO_GAME_MASTERS:
        if not db.get(GameMaster,gm_id):db.add(GameMaster(id=gm_id,display_name=name,home_location_id=location_id,source_system="DEMO"))
    db.flush();by_location={}
    for gm_id,_,location_id in DEMO_GAME_MASTERS:by_location.setdefault(location_id,[]).append(gm_id)
    rooms={r.id:r.location_id for r in db.scalars(select(Room)).all()}
    for session in db.scalars(select(Session)).all():
        options=by_location[rooms[session.room_id]];session.game_master_id=_pick(options,session.id)
        if session.requires_double_gm:
            second_options=[x for x in options if x!=session.game_master_id]
            session.second_game_master_id=_pick(second_options,session.id,1)
        else:session.second_game_master_id=None
    for gm in old:db.delete(gm)
    source=db.get(DataSource,"game_masters")
    if source:source.record_count=len(DEMO_GAME_MASTERS)
    db.commit();return True
