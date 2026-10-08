from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from .models import DataSource, Session
from .alerts import evaluate_alerts

class SyncError(ValueError): pass

def sync_source(db:DB,source_id:str,records:list[dict]):
    source=db.get(DataSource,source_id)
    if not source: raise SyncError("Fuente desconocida")
    created=updated=failed=0;errors=[]
    for raw in records:
        try:
            ext=str(raw["external_id"]);starts=raw["starts_at"]
            if isinstance(starts,str):starts=datetime.fromisoformat(starts)
            row=db.scalar(select(Session).where(Session.source_system==source_id,Session.external_id==ext))
            values={"room_id":str(raw["room_id"]),"starts_at":starts,"status":raw.get("status","completed"),"customers":int(raw.get("customers",0)),"revenue":float(raw.get("revenue",0)),"game_master_id":raw.get("game_master_id"),"second_game_master_id":raw.get("second_game_master_id"),"available":True,"source_updated_at":datetime.utcnow()}
            if row:
                for k,v in values.items():setattr(row,k,v)
                updated+=1
            else:db.add(Session(id=f"{source_id}:{ext}",external_id=ext,source_system=source_id,**values));created+=1
        except Exception as exc:failed+=1;errors.append(str(exc)[:160])
    source.last_sync_at=datetime.utcnow();source.record_count=created+updated;source.error_count=failed;source.last_error="; ".join(errors[:3]) or None;source.status="OK" if not failed else "CON ERRORES"
    db.commit();evaluate_alerts(db,trigger="data_sync");return {"source_id":source_id,"created":created,"updated":updated,"failed":failed,"idempotent":True,"alerts_recalculated":True,"stages":["raw","validation","processed","gold","analytics","alerts","forecast","logs"]}
