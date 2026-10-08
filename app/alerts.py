"""Deterministic WOM event engine: facts, gates, lifecycle and auditability."""
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB
from .config import settings
from .models import Alert, Room, Session

LAST_RUN={"evaluated_at":None,"trigger":None,"detectors":[],"candidates":0,"rejected":0,"created":0,"updated":0,"resolved":0,"errors":[]}
DETECTORS={
 "room_revenue_change":{"name":"Cambio relevante de facturación","source_module":"Finanzas / Salas","entity_type":"sala","metric":"revenue","period_days":28,"reference":"28 días inmediatamente anteriores","min_sample":settings.alerts_min_sample,"threshold":settings.alerts_revenue_deviation,"min_absolute":0,"limitations":"Facturación describe resultado observado; no demuestra causa."},
 "room_cancellation_change":{"name":"Cambio relevante de cancelaciones","source_module":"Demanda / Salas","entity_type":"sala","metric":"cancellation_rate","period_days":28,"reference":"28 días inmediatamente anteriores","min_sample":settings.alerts_min_sample,"threshold":settings.alerts_cancellation_deviation,"min_absolute":3,"limitations":"Exige además una diferencia mínima de 3 puntos porcentuales; no atribuye responsabilidad a personas."},
}
def relevance(deviation:float,sample_size:int,freshness_days:int=0)->tuple[float,float]:
    strength=min(1.0,sample_size/30);magnitude=min(50,abs(deviation));freshness=max(0,15-min(15,freshness_days))
    return round(strength,2),round(magnitude+strength*35+freshness,1)
def _active_for(db,base):return db.scalar(select(Alert).where(Alert.alert_key.like(f"{base}%"),Alert.status=="ACTIVE").order_by(Alert.detected_at.desc()))
def _next_key(db,base):
    count=len(db.scalars(select(Alert).where(Alert.alert_key.like(f"{base}%"))).all());return base if count==0 else f"{base}:{count+1}"
def _publish(db,contract,entity_id,title,current,baseline,n,evidence,start,end,trigger,negative_only=False):
    deviation=((current-baseline)/baseline*100) if baseline else 0;absolute=current-baseline
    gates={"data_quality":current is not None and baseline is not None,"comparability":start<=end,"evidence":n>=contract["min_sample"],"relevance":abs(deviation)>=contract["threshold"] and abs(absolute)>=contract["min_absolute"],"duplication":True}
    active=all(gates.values()) and not (negative_only and deviation<=0);suffix="cancel" if contract["metric"]=="cancellation_rate" else "revenue";base=f"room:{entity_id}:{suffix}";row=_active_for(db,base);now=datetime.utcnow()
    if not active:
        if row:row.status="RESOLVED";row.resolved_at=now;row.last_evaluated_at=now
        return "resolved" if row else "rejected"
    strength,score=relevance(deviation,n,(date.today()-end).days);event_type="EVOLUCIÓN POSITIVA" if deviation>0 and contract["metric"]!="cancellation_rate" else "REQUIERE ATENCIÓN" if score>=70 else "A VIGILAR";severity="positiva" if event_type=="EVOLUCIÓN POSITIVA" else "crítica" if score>=70 else "atención"
    if not row:
        key=_next_key(db,base);row=Alert(id=f"DYN-{key}",alert_key=key,category=contract["source_module"],severity=severity,title=title,explanation="",evidence="{}",period_start=start,period_end=end,detected_at=now);db.add(row);action="created"
    else:action="updated"
    direction="por encima" if deviation>0 else "por debajo";row.explanation=f"{contract['name']} en {entity_id}: {abs(deviation):.1f} % {direction} de su referencia comparable. Los datos disponibles no permiten determinar la causa."
    row.title=title;row.category=contract["source_module"];row.status="ACTIVE";row.resolved_at=None;row.last_evaluated_at=now;row.current_value=current;row.baseline_value=baseline;row.deviation=round(deviation,2);row.evidence_strength=strength;row.relevance_score=score;row.severity=severity
    row.evidence=json.dumps({**evidence,"detector_id":contract["id"],"event_type":event_type,"entity_type":contract["entity_type"],"entity_id":entity_id,"metric":contract["metric"],"actual":current,"reference":baseline,"absolute_difference":round(absolute,2),"relative_difference":round(deviation,2),"sample_size":n,"period":{"start":str(start),"end":str(end)},"reference_period":contract["reference"],"gates":gates,"source_module":contract["source_module"],"trigger":trigger,"limitations":contract["limitations"]},ensure_ascii=False);return action
def evaluate_alerts(db:DB,as_of:date|None=None,trigger:str="manual"):
    end=as_of or date.today();start=end-timedelta(days=27);prev_end=start-timedelta(days=1);prev_start=prev_end-timedelta(days=27);audit={"evaluated_at":datetime.utcnow(),"trigger":trigger,"detectors":list(DETECTORS),"candidates":0,"rejected":0,"created":0,"updated":0,"resolved":0,"errors":[]}
    for room in db.scalars(select(Room)).all():
      try:
        def stats(a,b):
            rows=db.scalars(select(Session).where(Session.room_id==room.id,func.date(Session.starts_at)>=a,func.date(Session.starts_at)<=b)).all();booked=[x for x in rows if x.status in ("completed","cancelled")]
            return sum(x.revenue for x in rows if x.status=="completed"),sum(x.status=="cancelled" for x in booked)/len(booked)*100 if booked else 0,len(booked)
        cur_rev,cur_cancel,n=stats(start,end);base_rev,base_cancel,_=stats(prev_start,prev_end)
        for detector_id,current,baseline,title,negative_only in (("room_revenue_change",cur_rev,base_rev,f"Facturación fuera de referencia · {room.name}",False),("room_cancellation_change",cur_cancel,base_cancel,f"Cancelaciones elevadas · {room.name}",True)):
            audit["candidates"]+=1;action=_publish(db,{"id":detector_id,**DETECTORS[detector_id]},room.id,title,current,baseline,n,{"room_id":room.id},start,end,trigger,negative_only);audit[action]+=1
      except Exception as exc:audit["errors"].append({"room_id":room.id,"error":str(exc)[:200]})
    db.commit();LAST_RUN.update(audit);return db.scalars(select(Alert).order_by(Alert.relevance_score.desc())).all()
def engine_status(db:DB):
    counts={"attention":0,"watch":0,"positive":0,"insight":0,"resolved":0}
    for row in db.scalars(select(Alert)).all():
        if row.status=="RESOLVED":counts["resolved"]+=1;continue
        event=json.loads(row.evidence or '{}').get('event_type','A VIGILAR');counts[{"REQUIERE ATENCIÓN":"attention","A VIGILAR":"watch","EVOLUCIÓN POSITIVA":"positive","INSIGHT":"insight"}.get(event,"watch")]+=1
    tz=ZoneInfo(settings.timezone);now=datetime.now(tz);next_summary=now.replace(hour=9,minute=0,second=0,microsecond=0)+(timedelta(days=1) if now.hour>=9 else timedelta())
    return {"counts":counts,"last_run":LAST_RUN,"next_daily_summary":next_summary,"timezone":settings.timezone,"demo":True,"algorithm":"deterministic"}
