from collections import defaultdict
from calendar import monthrange
from datetime import date, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from .demand_map import demand_map
from .models import Expense, Room, Session

METRICS={
 "revenue":("Ingresos","EUR","metric-revenue"),"expenses":("Gastos","EUR","metric-expenses"),
 "profit":("Beneficio","EUR","metric-profit"),"margin":("Margen","percent","metric-margin"),
 "reservations":("Reservas","count","metric-reservations"),"sessions":("Sesiones","count","metric-sessions"),
 "customers":("Clientes / jugadores","count","metric-customers"),"cancellations":("Cancelaciones","count","metric-cancellations"),
 "average_ticket":("Ticket medio","EUR","metric-average-ticket"),"occupancy":("Ocupación","percent","metric-occupancy"),
 "players_per_reservation":("Jugadores / reserva","count","metric-players-reservation"),
 "cancellation_rate":("Tasa de cancelación","percent","metric-cancellation-rate"),
 "revenue_per_slot":("Ingreso / slot disponible","EUR","metric-revenue-slot")}

def choose_granularity(start:date,end:date,requested="auto"):
    if requested!="auto":return requested
    days=(end-start).days+1
    if days<=62:return "day"
    if days<=730:return "month"
    return "quarter"

def _bucket(d:date,granularity:str):
    if granularity=="day":return d.isoformat()
    if granularity=="week":
        monday=d-timedelta(days=d.weekday());return monday.isoformat()
    if granularity=="month":return f"{d.year}-{d.month:02}"
    return f"{d.year}-T{(d.month-1)//3+1}"

def business_timeseries(db:DB,start:date,end:date,metrics:list[str],granularity="auto",scope_type="company",scope_id=None,expense_view="accounting"):
    if start>end:raise ValueError("La fecha de inicio no puede ser posterior a la fecha fin")
    unknown=[m for m in metrics if m not in METRICS]
    if unknown:raise ValueError(f"Métricas no permitidas: {', '.join(unknown)}")
    if scope_type not in {"company","location","room"}:raise ValueError("Ámbito no permitido")
    if expense_view not in {"accounting","accrued"}:raise ValueError("Vista de gastos no permitida")
    if scope_type!="company" and not scope_id:raise ValueError("El ámbito seleccionado requiere scope_id")
    granularity=choose_granularity(start,end,granularity)
    rooms={r.id:r.location_id for r in db.scalars(select(Room)).all()}
    def in_scope(room_id):return scope_type=="company" or (scope_type=="room" and room_id==scope_id) or (scope_type=="location" and rooms.get(room_id)==scope_id)
    sessions=[s for s in db.scalars(select(Session).where(Session.starts_at>=datetime.combine(start,datetime.min.time()),Session.starts_at<datetime.combine(end+timedelta(days=1),datetime.min.time()))).all() if in_scope(s.room_id)]
    expense_start=date(start.year,start.month,1) if expense_view=="accrued" else start
    expenses=[x for x in db.scalars(select(Expense).where(Expense.expense_date>=expense_start,Expense.expense_date<=end,Expense.voided==False)).all() if scope_type=="company" or (scope_type=="location" and x.location_id==scope_id) or (scope_type=="room" and x.room_id==scope_id)]
    agg=defaultdict(lambda:{"revenue":0.0,"expenses":0.0,"reservations":0,"sessions":0,"customers":0,"cancellations":0,"available":0})
    uses_reference_offer=any(metric in {"occupancy","revenue_per_slot"} for metric in metrics)
    mapped=demand_map(db,start,end,location_id=scope_id if scope_type=="location" else None,room_id=scope_id if scope_type=="room" else None) if uses_reference_offer else None
    if mapped and mapped["rooms"]:
        for day in mapped["calendar"]:
            agg[_bucket(date.fromisoformat(day["date"]),granularity)]["available"]+=sum(cell["available"] for cell in day["cells"])
    legacy_availability=uses_reference_offer and not (mapped and mapped["rooms"])
    for s in sessions:
        a=agg[_bucket(s.starts_at.date(),granularity)];a["available"]+=int(legacy_availability and bool(s.available));a["sessions"]+=int(s.status in {"completed","cancelled"});a["cancellations"]+=int(s.status=="cancelled")
        if s.status=="completed":a["revenue"]+=s.revenue;a["reservations"]+=1;a["customers"]+=s.customers
    for x in expenses:
        if expense_view=="accrued" and x.recurring and x.periodicity in {"monthly","mensual"}:
            days=monthrange(x.expense_date.year,x.expense_date.month)[1];daily=x.amount/days
            for day in range(1,days+1):
                d=date(x.expense_date.year,x.expense_date.month,day)
                if start<=d<=end:agg[_bucket(d,granularity)]["expenses"]+=daily
        elif start<=x.expense_date<=end:agg[_bucket(x.expense_date,granularity)]["expenses"]+=x.amount
    series=[]
    for label,a in sorted(agg.items()):
        profit=a["revenue"]-a["expenses"]
        values={**a,"profit":profit,"margin":profit/a["revenue"]*100 if a["revenue"] else None,"average_ticket":a["revenue"]/a["customers"] if a["customers"] else None,"occupancy":a["reservations"]/a["available"]*100 if a["available"] else None,"players_per_reservation":a["customers"]/a["reservations"] if a["reservations"] else None,"cancellation_rate":a["cancellations"]/a["sessions"]*100 if a["sessions"] else None,"revenue_per_slot":a["revenue"]/a["available"] if a["available"] else None}
        series.append({"date":label,"values":{m:round(values[m],2) if values[m] is not None else None for m in metrics}})
    totals={}
    revenue=sum(a["revenue"] for a in agg.values());expenses_total=sum(a["expenses"] for a in agg.values());customers=sum(a["customers"] for a in agg.values());reservations=sum(a["reservations"] for a in agg.values());available=sum(a["available"] for a in agg.values())
    sessions_total=sum(a["sessions"] for a in agg.values());cancellations_total=sum(a["cancellations"] for a in agg.values())
    base={"revenue":revenue,"expenses":expenses_total,"profit":revenue-expenses_total,"margin":((revenue-expenses_total)/revenue*100 if revenue else None),"reservations":reservations,"sessions":sessions_total,"customers":customers,"cancellations":cancellations_total,"average_ticket":revenue/customers if customers else None,"occupancy":reservations/available*100 if available else None,"players_per_reservation":customers/reservations if reservations else None,"cancellation_rate":cancellations_total/sessions_total*100 if sessions_total else None,"revenue_per_slot":revenue/available if available else None}
    for m in metrics:totals[m]=round(base[m],2) if base[m] is not None else None
    annotations=[]
    if expense_view=="accounting" and "expenses" in metrics and expenses:
        by_day=defaultdict(list)
        for x in expenses:by_day[x.expense_date].append(x)
        peak_day,peak_rows=max(by_day.items(),key=lambda item:sum(x.amount for x in item[1]))
        recurring=[x for x in peak_rows if x.recurring and x.periodicity in {"monthly","mensual"}]
        if recurring and sum(x.amount for x in recurring)>=sum(x.amount for x in peak_rows)*.8:
            annotations.append({"date":_bucket(peak_day,granularity),"metric":"expenses","label":f"{len(recurring)} gastos mensuales recurrentes","value":round(sum(x.amount for x in peak_rows),2)})
    return {"period":{"start":start,"end":end},"granularity":granularity,"scope":{"type":scope_type,"id":scope_id},"expense_view":expense_view,"metrics":[{"key":m,"label":METRICS[m][0],"unit":METRICS[m][1],"color_token":METRICS[m][2]} for m in metrics],"series":series,"totals":totals,"annotations":annotations,"empty":not bool(series)}
