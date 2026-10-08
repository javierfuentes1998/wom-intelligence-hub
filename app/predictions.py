"""V2.8 business forecasts: explicit, deterministic and auditable."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import floor

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from .models import Room, Session

WEEK_WEIGHTS=(.5,.5)
MONTH_WEIGHTS=(.7,.3)


def _commercial_round(value: float) -> int:
    """Executive integer rounding: decimal half-up, independent of float noise."""
    return int(Decimal(str(round(value,2))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _month_start(value: date) -> date: return value.replace(day=1)
def _add_month(value: date, step: int) -> date:
    index=value.year*12+value.month-1+step
    return date(index//12,index%12+1,1)
def _month_end(value: date) -> date: return value.replace(day=monthrange(value.year,value.month)[1])
def _period_label(start: date,end: date) -> str: return f"{start.isoformat()} — {end.isoformat()}"


def _filters(start: date,end: date,location_id=None,room_id=None):
    out=[func.date(Session.starts_at)>=start,func.date(Session.starts_at)<=end,Session.status=="completed"]
    if room_id: out.append(Session.room_id==room_id)
    elif location_id: out.append(Session.room_id.in_(select(Room.id).where(Room.location_id==location_id)))
    return out


def _totals(db: DB,start: date,end: date,location_id=None,room_id=None) -> dict:
    rows=db.scalars(select(Session).where(*_filters(start,end,location_id,room_id))).all()
    return {"reservations":len(rows),"revenue":round(sum(row.revenue for row in rows),2)}


def _daily(db: DB,start: date,end: date,location_id=None,room_id=None) -> list[dict]:
    grouped={start+timedelta(days=i):{"reservations":0.0,"revenue":0.0} for i in range((end-start).days+1)}
    for row in db.scalars(select(Session).where(*_filters(start,end,location_id,room_id))).all():
        day=row.starts_at.date();grouped[day]["reservations"]+=1;grouped[day]["revenue"]+=row.revenue
    return [{"date":str(day),"reservations":values["reservations"],"revenue":round(values["revenue"],2)} for day,values in grouped.items()]


def _resample(values: list[float], target_length: int) -> list[float]:
    """Move a source distribution to N calendar days using interval overlap.

    This preserves the exact source total and never invents an invalid date.
    """
    if not values or target_length<=0:return []
    source_length=len(values);result=[0.0]*target_length
    for source_index,value in enumerate(values):
        left=source_index/source_length;right=(source_index+1)/source_length
        first=floor(left*target_length);last=min(target_length-1,floor((right*target_length)-1e-12))
        for target_index in range(first,last+1):
            overlap=max(0.0,min(right,(target_index+1)/target_length)-max(left,target_index/target_length))
            result[target_index]+=value*overlap*source_length
    return result


def _variation(value: float,reference: float) -> float|None:
    return round((value-reference)/reference*100,1) if reference else None


def _scope_start(db:DB,location_id=None,room_id=None) -> date|None:
    q=select(func.min(Session.starts_at)).where(Session.status=="completed")
    if room_id:q=q.where(Session.room_id==room_id)
    elif location_id:q=q.where(Session.room_id.in_(select(Room.id).where(Room.location_id==location_id)))
    value=db.scalar(q);return value.date() if value else None


def _reference_available(scope_start:date|None,start:date,end:date,last_date:date) -> bool:
    return bool(scope_start and start>=scope_start and end<=last_date)


def _prediction_component(annual:float,recent:float,annual_ok:bool,recent_ok:bool,weights:tuple[float,float]):
    if annual_ok and recent_ok:return annual*weights[0]+recent*weights[1],"complete",weights
    if annual_ok:return annual,"provisional_annual_only",(1.0,0.0)
    if recent_ok:return recent,"provisional_recent_only",(0.0,1.0)
    return None,"insufficient_data",(0.0,0.0)


def _strong_days(points:list[dict]) -> list[str]:
    if not points:return []
    average=sum(x["prediction"]["reservations"] for x in points)/len(points)
    ranked=sorted(points,key=lambda x:x["prediction"]["reservations"],reverse=True)[:2]
    return [x["label"] for x in ranked] if average and all(x["prediction"]["reservations"]>=average*1.15 for x in ranked) else []


def _aggregate_weeks(points:list[dict]) -> list[dict]:
    out=[]
    for point in points:
        day=date.fromisoformat(point["date"]);key=f"Semana {(day.day-1)//7+1}"
        if not out or out[-1]["label"]!=key:out.append({"label":key,"start":point["date"],"end":point["date"],"annual":{"reservations":0.0,"revenue":0.0},"recent":{"reservations":0.0,"revenue":0.0},"prediction":{"reservations":0.0,"revenue":0.0}})
        target=out[-1];target["end"]=point["date"]
        for series in ("annual","recent","prediction"):
            for metric in ("reservations","revenue"):target[series][metric]+=point[series][metric]
    for item in out:
        for series in ("annual","recent","prediction"):
            item[series]["reservations"]=round(item[series]["reservations"],2);item[series]["revenue"]=round(item[series]["revenue"],2)
    return out

def _allocate_integer(values:list[float], total:int) -> list[int]:
    """Largest-remainder allocation for discrete executive reservation labels."""
    if not values:return []
    floors=[floor(v) for v in values];remaining=max(0,total-sum(floors))
    order=sorted(range(len(values)),key=lambda i:(values[i]-floors[i],-i),reverse=True)
    for i in order[:remaining]:floors[i]+=1
    return floors


def business_prediction(db:DB,mode="week",location_id=None,room_id=None) -> dict:
    if room_id:
        room=db.get(Room,room_id)
        if not room:raise ValueError("Sala no válida")
        if location_id and room.location_id!=location_id:raise ValueError("La sala no pertenece al local seleccionado")
    last_dt=db.scalar(select(func.max(Session.starts_at)).where(Session.status=="completed"))
    if not last_dt:return {"status":"insufficient_data","mode":mode,"demo":True,"message":"No hay histórico disponible."}
    last_date=last_dt.date();scope_start=_scope_start(db,location_id,room_id)
    if mode=="week":
        target_start=last_date+timedelta(days=7-last_date.weekday());target_end=target_start+timedelta(days=6)
        last_complete_end=last_date-timedelta(days=last_date.weekday()+1)
        recent_end=last_complete_end;recent_start=recent_end-timedelta(days=6)
        annual_start=target_start-timedelta(days=364);annual_end=target_end-timedelta(days=364);weights=WEEK_WEIGHTS
    elif mode=="month":
        current_start=_month_start(last_date)
        target_start=_add_month(current_start,1);target_end=_month_end(target_start)
        recent_start=current_start if last_date==_month_end(last_date) else _add_month(current_start,-1)
        recent_end=_month_end(recent_start)
        annual_start=target_start.replace(year=target_start.year-1);annual_end=_month_end(annual_start);weights=MONTH_WEIGHTS
    else:raise ValueError("El modo debe ser week o month")
    annual_ok=_reference_available(scope_start,annual_start,annual_end,last_date);recent_ok=_reference_available(scope_start,recent_start,recent_end,last_date)
    annual=_totals(db,annual_start,annual_end,location_id,room_id) if annual_ok else {"reservations":0,"revenue":0.0}
    recent=_totals(db,recent_start,recent_end,location_id,room_id) if recent_ok else {"reservations":0,"revenue":0.0}
    predictions={};status="complete"
    for metric in ("reservations","revenue"):
        value,metric_status,applied=_prediction_component(annual[metric],recent[metric],annual_ok,recent_ok,weights)
        predictions[metric]={"exact":round(value,2) if value is not None else None,"display":_commercial_round(value) if value is not None else None,"status":metric_status,"applied_weights":applied}
        if metric_status!="complete":status=metric_status
    annual_days=_daily(db,annual_start,annual_end,location_id,room_id) if annual_ok else []
    recent_days=_daily(db,recent_start,recent_end,location_id,room_id) if recent_ok else []
    target_count=(target_end-target_start).days+1
    points=[]
    for metric in ("reservations","revenue"):
        a=_resample([x[metric] for x in annual_days],target_count) if annual_ok else [0.0]*target_count
        r=_resample([x[metric] for x in recent_days],target_count) if recent_ok else [0.0]*target_count
        applied=predictions[metric]["applied_weights"]
        for i in range(target_count):
            if len(points)<=i:points.append({"date":str(target_start+timedelta(days=i)),"label":["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][(target_start+timedelta(days=i)).weekday()],"annual":{},"recent":{},"prediction":{}})
            points[i]["annual"][metric]=round(a[i],2);points[i]["recent"][metric]=round(r[i],2);points[i]["prediction"][metric]=round(a[i]*applied[0]+r[i]*applied[1],2)
    chart=points if mode=="week" else _aggregate_weeks(points)
    reservation_display=_allocate_integer([x["prediction"]["reservations"] for x in chart],predictions["reservations"]["display"] or 0)
    for item,display in zip(chart,reservation_display):item["prediction_display_reservations"]=display
    return {"status":status,"mode":mode,"demo":True,"last_available_date":str(last_date),
        "scope":{"location_id":location_id,"room_id":room_id,"start":str(scope_start) if scope_start else None},
        "target":{"start":str(target_start),"end":str(target_end),"label":_period_label(target_start,target_end)},
        "references":{"annual":{"start":str(annual_start),"end":str(annual_end),"available":annual_ok,**annual},"recent":{"start":str(recent_start),"end":str(recent_end),"available":recent_ok,**recent}},
        "weights":{"annual":weights[0],"recent":weights[1]},"prediction":predictions,
        "variations":{"annual":{m:_variation(predictions[m]["exact"],annual[m]) if predictions[m]["exact"] is not None and annual_ok else None for m in predictions},"recent":{m:_variation(predictions[m]["exact"],recent[m]) if predictions[m]["exact"] is not None and recent_ok else None for m in predictions}},
        "daily":points,"chart":chart,"strong_days":_strong_days(points) if mode=="week" and status=="complete" else [],
        "method":{"rule":"0,50 × mismo periodo año anterior + 0,50 × periodo anterior" if mode=="week" else "0,70 × mismo mes año anterior + 0,30 × mes anterior","rounding":"Los cálculos conservan decimales; KPI de reservas y facturación se redondean al entero más próximo.","annual_alignment":"Semanas alineadas lunes-domingo desplazando 364 días, lo que conserva el día de semana incluso en cambios de año ISO." if mode=="week" else "Mismo mes natural del año anterior.","monthly_distribution":"Las distribuciones diarias de ambos meses de referencia se reescalan proporcionalmente al número de días del mes objetivo; se conserva cada total y no se crean fechas inexistentes." if mode=="month" else None},
        "limitations":["Estimación basada únicamente en dos periodos históricos; no demuestra causalidad.","Los datos son DEMO y no representan previsiones reales de WOM.","El último periodo parcial se excluye como referencia completa."]}
