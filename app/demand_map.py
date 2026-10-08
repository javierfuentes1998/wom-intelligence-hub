from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .models import Room, Session
from .schedules import REFERENCE_SCHEDULES, SCHEDULE_SOURCE


def _days(start:date,end:date):
    current=start
    while current<=end:
        yield current;current+=timedelta(days=1)


def _level(reservations,available):
    if not available:return {"key":"unavailable","label":"Sesión no disponible","ratio":None}
    ratio=reservations/available
    if ratio==0:key,label="no_demand","Sin demanda"
    elif ratio<.25:key,label="low","Baja"
    elif ratio<.5:key,label="medium","Media"
    elif ratio<1:key,label="high","Alta"
    else:key,label="maximum","Máxima"
    return {"key":key,"label":label,"ratio":round(ratio,3)}


def _reference_assignment(rows,room_id):
    """Project legacy DEMO rows onto configured reference slots without changing totals.

    Real integrations use exact timestamps. The legacy seed used generic integer hours;
    the deterministic ordinal projection is limited to DEMO rows whose time is not an
    exact configured slot.
    """
    times=REFERENCE_SCHEDULES[room_id];ordered=sorted(rows,key=lambda x:x.starts_at)
    exact={x.starts_at.strftime("%H:%M") for x in ordered}
    if exact.issubset(set(times)):return [(x,x.starts_at.strftime("%H:%M")) for x in ordered]
    if len(ordered)==1:indexes=[len(times)//2]
    else:indexes=[round(i*(len(times)-1)/(len(ordered)-1)) for i in range(len(ordered))]
    return [(row,times[index]) for row,index in zip(ordered,indexes)]


def demand_map(db:DB,start:date,end:date,location_id=None,room_id=None):
    rooms=db.scalars(select(Room).order_by(Room.location_id,Room.name)).all()
    rooms=[r for r in rooms if r.id in REFERENCE_SCHEDULES and (not location_id or r.location_id==location_id) and (not room_id or r.id==room_id)]
    room_ids={r.id for r in rooms};hours=sorted({h for r in rooms for h in REFERENCE_SCHEDULES[r.id]})
    rows=db.scalars(select(Session).where(Session.room_id.in_(room_ids),Session.starts_at>=datetime.combine(start,datetime.min.time()),Session.starts_at<datetime.combine(end+timedelta(days=1),datetime.min.time()))).all() if room_ids else []
    by_room_day=defaultdict(list)
    for row in rows:by_room_day[(row.room_id,row.starts_at.date())].append(row)
    cells=defaultdict(lambda:{"available":0,"reservations":0,"players":0,"revenue":0.0,"cancellations":0,"rooms":set()})
    calendar=[]
    for day in _days(start,end):
        day_cells=[]
        assignments={}
        for room in rooms:
            assigned=defaultdict(list)
            for session,slot in _reference_assignment(by_room_day.get((room.id,day),[]),room.id):assigned[slot].append(session)
            assignments[room.id]=assigned
        for hour in hours:
            cell={"date":str(day),"weekday":day.weekday(),"hour":hour,"available":0,"reservations":0,"players":0,"revenue":0.0,"cancellations":0,"rooms":set()}
            for room in rooms:
                if hour not in REFERENCE_SCHEDULES[room.id]:continue
                slot_rows=assignments[room.id].get(hour,[])
                # One configured room/day/time is one commercial opportunity.
                # Several legacy DEMO rows may be projected onto it, but they must
                # never invent additional offered sessions or alter the denominator.
                cell["available"]+=1;cell["rooms"].add(room.id)
                for session in slot_rows:
                    if session.status=="completed":cell["reservations"]+=1;cell["players"]+=session.customers;cell["revenue"]+=session.revenue
                    elif session.status=="cancelled":cell["cancellations"]+=1
            level=_level(cell["reservations"],cell["available"]);cell["rooms"]=sorted(cell["rooms"]);cell["occupancy"]=round(level["ratio"]*100,1) if level["ratio"] is not None else None;cell["demand"]=level
            day_cells.append(cell)
            if cell["available"]:
                weekly=cells[(day.weekday(),hour)]
                for key in ("available","reservations","players","revenue","cancellations"):weekly[key]+=cell[key]
                weekly["rooms"].update(cell["rooms"])
        calendar.append({"date":str(day),"weekday":day.weekday(),"cells":day_cells})
    pattern=[]
    for weekday in range(7):
        row=[]
        for hour in hours:
            value=cells[(weekday,hour)];level=_level(value["reservations"],value["available"])
            row.append({"weekday":weekday,"hour":hour,"available":value["available"],"reservations":value["reservations"],"players":value["players"],"revenue":round(value["revenue"],2),"cancellations":value["cancellations"],"rooms":sorted(value["rooms"]),"occupancy":round(level["ratio"]*100,1) if level["ratio"] is not None else None,"demand":level})
        pattern.append({"weekday":weekday,"cells":row})
    totals={"available":sum(x["available"] for d in calendar for x in d["cells"]),"reservations":sum(x["reservations"] for d in calendar for x in d["cells"]),"players":sum(x["players"] for d in calendar for x in d["cells"]),"revenue":round(sum(x["revenue"] for d in calendar for x in d["cells"]),2),"cancellations":sum(x["cancellations"] for d in calendar for x in d["cells"])}
    totals["occupancy"]=round(totals["reservations"]/totals["available"]*100,2) if totals["available"] else None
    weekend=sum(x["reservations"] for d in calendar if d["weekday"]>=4 for x in d["cells"]);totals["weekend_share"]=round(weekend/totals["reservations"]*100,1) if totals["reservations"] else None
    return {"period":{"start":start,"end":end},"scope":{"location_id":location_id,"room_id":room_id},"source":SCHEDULE_SOURCE,"projection":"Los datos DEMO originales no incluyen los horarios comerciales reales de cada reserva. Para visualizar el mapa, las reservas sintéticas se distribuyen de forma reproducible exclusivamente entre los horarios oficiales de su sala, sin modificar sus totales.","rooms":[{"id":r.id,"name":r.name,"location_id":r.location_id,"hours":REFERENCE_SCHEDULES[r.id]} for r in rooms],"hours":hours,"weekly":pattern,"calendar":calendar,"totals":totals,"definitions":{"unavailable":"No existe una sesión ofrecida para esta sala, fecha y hora.","zero":"La sesión estaba ofrecida y no recibió una reserva completada.","occupancy":"Ocupación DEMO = sesiones reservadas / sesiones oficialmente ofrecidas × 100.","demand":"Intensidad de utilización de las sesiones ofrecidas: 0 % sin demanda; >0 y <25 % baja; 25–<50 % media; 50–<100 % alta; 100 % máxima."}}
