import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from .analytics import comparison
from .demand_map import demand_map
from .models import Alert, GameMaster, Room, Session
from .service import kpis

HEALTH_WEIGHTS={"revenue_trend":.40,"occupancy":.40,"cancellations":.20}

def _clamp(value):return max(0.0,min(100.0,float(value)))

def _health(revenue_trend,occupancy,cancellation_rate):
    observed={"revenue_trend":revenue_trend,"occupancy":occupancy,"cancellations":cancellation_rate}
    normalized={"revenue_trend":None if revenue_trend is None else _clamp(50+revenue_trend*2),"occupancy":None if occupancy is None else _clamp(occupancy),"cancellations":None if cancellation_rate is None else _clamp(100-cancellation_rate)}
    available=[key for key,value in normalized.items() if value is not None];weight_total=sum(HEALTH_WEIGHTS[key] for key in available)
    components=[];score=0
    for key in HEALTH_WEIGHTS:
        effective=HEALTH_WEIGHTS[key]/weight_total if key in available and weight_total else 0;contribution=None if normalized[key] is None else normalized[key]*effective
        if contribution is not None:score+=contribution
        components.append({"key":key,"observed":observed[key],"normalized":None if normalized[key] is None else round(normalized[key],1),"base_weight":HEALTH_WEIGHTS[key],"effective_weight":round(effective,4),"contribution":None if contribution is None else round(contribution,1),"status":"available" if key in available else "not_evaluable"})
    return {"score":round(score,1) if available else None,"experimental":True,"complete":len(available)==len(HEALTH_WEIGHTS),"components":components,"formula":"Suma de componente normalizado × peso efectivo; si falta un componente, no se convierte en cero y los pesos disponibles se renormalizan."}

def room_detail(db:DB,room_id:str,start:date,end:date):
    room=db.get(Room,room_id)
    if not room:raise ValueError("Sala no encontrada")
    rows=db.scalars(select(Session).where(Session.room_id==room_id,Session.starts_at>=datetime.combine(start,datetime.min.time()),Session.starts_at<datetime.combine(end+timedelta(days=1),datetime.min.time())).order_by(Session.starts_at)).all()
    completed=[x for x in rows if x.status=="completed"];booked=[x for x in rows if x.status in {"completed","cancelled"}];available=len(rows);cancelled=[x for x in booked if x.status=="cancelled"]
    mapped=demand_map(db,start,end,room_id=room_id);available=mapped["totals"]["available"]
    revenue=round(sum(x.revenue for x in completed),2);players=sum(x.customers for x in completed);reservations=len(completed);cancellation_rate=round(len(cancelled)/len(booked)*100,2) if booked else None;occupancy=round(reservations/available*100,2) if available else None
    metrics=kpis(db,start,end,room_id=room_id)["kpis"];year_change=metrics["revenue"]["year_comparison"]["percent"]
    weekdays={i:{"weekday":i,"available":0,"reservations":0,"players":0} for i in range(7)};hours=defaultdict(lambda:{"available":0,"reservations":0,"players":0});heat=defaultdict(lambda:{"available":0,"reservations":0})
    groups=defaultdict(int);gm_data=defaultdict(lambda:{"sessions":0,"players":0,"cancellations":0})
    for row in rows:
        wd=row.starts_at.weekday();hour=row.starts_at.hour;weekdays[wd]["available"]+=1;hours[hour]["available"]+=1;heat[(wd,hour)]["available"]+=1
        if row.status=="completed":
            weekdays[wd]["reservations"]+=1;weekdays[wd]["players"]+=row.customers;hours[hour]["reservations"]+=1;hours[hour]["players"]+=row.customers;heat[(wd,hour)]["reservations"]+=1;groups[row.customers]+=1
        for gm_id in {row.game_master_id,row.second_game_master_id}-{None}:
            gm_data[gm_id]["sessions"]+=int(row.status=="completed");gm_data[gm_id]["players"]+=row.customers if row.status=="completed" else 0;gm_data[gm_id]["cancellations"]+=int(row.status=="cancelled")
    weekday_data=[{**x,"occupancy":round(x["reservations"]/x["available"]*100,1) if x["available"] else None} for x in weekdays.values()]
    hour_data=[{"hour":hour,**x,"occupancy":round(x["reservations"]/x["available"]*100,1) if x["available"] else None} for hour,x in sorted(hours.items())]
    heatmap=[{"weekday":wd,"hour":hour,"available":x["available"],"reservations":x["reservations"],"occupancy":round(x["reservations"]/x["available"]*100,1) if x["available"] else None} for (wd,hour),x in sorted(heat.items())]
    gms=[]
    for gm_id,data in gm_data.items():
        gm=db.get(GameMaster,gm_id);gms.append({"id":gm_id,"name":gm.display_name if gm else gm_id,**data})
    gms.sort(key=lambda x:(-x["sessions"],x["name"]))
    alerts=[]
    for alert in db.scalars(select(Alert).where(Alert.status=="ACTIVE").order_by(Alert.relevance_score.desc())).all():
        evidence=json.loads(alert.evidence)
        if evidence.get("room_id")!=room_id:continue
        positive=evidence.get("metric")=="revenue" and (alert.deviation or 0)>0
        tone="opportunity" if positive else "critical" if alert.severity=="crítica" else "warning" if (alert.deviation or 0)<0 or evidence.get("metric")=="cancellation_rate" else "information"
        alerts.append({"id":alert.id,"title":alert.title,"tone":tone,"label":{"opportunity":"Oportunidad","critical":"Crítica","warning":"Advertencia","information":"Información"}[tone],"deviation":alert.deviation,"sample_size":evidence.get("sample_size"),"relevance":alert.relevance_score,"explanation":alert.explanation})
    health=_health(metrics["revenue"]["comparison"]["percent"],occupancy,cancellation_rate)
    return {"room":{"id":room.id,"name":room.name,"location_id":room.location_id,"capacity":room.capacity,"experience_type":room.experience_type},"period":{"start":start,"end":end},"kpis":{"revenue":revenue,"reservations":reservations,"players":players,"available_slots":available,"occupancy":occupancy,"average_ticket":round(revenue/players,2) if players else None,"players_per_reservation":round(players/reservations,2) if reservations else None,"cancellations":len(cancelled),"booked_slots":len(booked),"cancellation_rate":cancellation_rate,"year_revenue_change":year_change,"revenue_per_available_slot":round(revenue/available,2) if available else None},"demand":{"weekdays":weekday_data,"hours":hour_data,"heatmap":heatmap,"availability_source":"Horario configurado de referencia · DEMO V3"},"group_distribution":[{"players":size,"reservations":count} for size,count in sorted(groups.items())],"game_masters":gms,"voc":{"count":0,"rating":None,"positive":0,"neutral":0,"negative":0,"topics":[]},"health":health,"alerts":alerts,"definitions":{"occupancy":"Reservas completadas / sesiones ofrecidas de referencia","cancellations":"Cancelaciones / (completadas + canceladas)","average_ticket":"Ingresos / jugadores","players_per_reservation":"Jugadores / reservas completadas","revenue_per_available_slot":"Ingresos / sesiones ofrecidas de referencia"}}
