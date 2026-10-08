import json, uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from calendar import monthrange
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session as DB
from .analytics import backtest_seasonal, comparison, robust_anomalies, room_health, safe_margin, seasonal_naive
from .demand_map import demand_map
from .models import Expense, ExpenseCategory, Location, Review, Room, Session

def bounds(start: date|None,end: date|None):
    end=end or date.today(); start=start or end-timedelta(days=29); return start,end
def session_filters(start,end,location_id=None,room_id=None):
    q=[func.date(Session.starts_at)>=start,func.date(Session.starts_at)<=end]
    if room_id:q.append(Session.room_id==room_id)
    if location_id:q.append(Session.room_id.in_(select(Room.id).where(Room.location_id==location_id)))
    return q
def kpis(db:DB,start=None,end=None,location_id=None,room_id=None):
    start,end=bounds(start,end);days=(end-start).days+1
    if start.day==1 and end==date(start.year,start.month,monthrange(start.year,start.month)[1]):
        py=start.year if start.month>1 else start.year-1;pm=start.month-1 if start.month>1 else 12;ps=date(py,pm,1);pe=date(py,pm,monthrange(py,pm)[1])
    elif start==date(start.year,1,1) and end==date(start.year,12,31):ps,pe=date(start.year-1,1,1),date(start.year-1,12,31)
    else:ps=start-timedelta(days=days);pe=start-timedelta(days=1)
    try:ys,ye=start.replace(year=start.year-1),end.replace(year=end.year-1)
    except ValueError:ys,ye=start.replace(year=start.year-1,day=28),end.replace(year=end.year-1,day=28)
    def period(a,b):
        rows=db.execute(select(Session).where(*session_filters(a,b,location_id,room_id))).scalars().all(); completed=[r for r in rows if r.status=="completed"]
        exq=select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.voided==False,Expense.expense_date>=a,Expense.expense_date<=b)
        if location_id:exq=exq.where(Expense.location_id==location_id)
        if room_id:exq=exq.where(Expense.room_id==room_id)
        expenses=float(db.scalar(exq) or 0); revenue=sum(r.revenue for r in completed); customers=sum(r.customers for r in completed); mapped=demand_map(db,a,b,location_id,room_id);available=mapped["totals"]["available"] if mapped["rooms"] else sum(1 for r in rows if r.available)
        reservations=len(completed); profit=revenue-expenses
        return {"revenue":round(revenue,2),"expenses":round(expenses,2),"profit":round(profit,2),"margin":safe_margin(revenue,profit),"reservations":reservations,"customers":customers,"average_ticket":round(revenue/customers,2) if customers else None,"occupancy":round(reservations/available*100,2) if available else None,"revenue_per_session":round(revenue/reservations,2) if reservations else None,"revenue_per_customer":round(revenue/customers,2) if customers else None}
    cur,prev,year_prev=period(start,end),period(ps,pe),period(ys,ye)
    return {"period":{"start":start,"end":end,"previous":{"start":ps,"end":pe},"previous_year":{"start":ys,"end":ye}},"demo":True,"kpis":{k:{"value":v,"previous":prev[k],"previous_year":year_prev[k],"comparison":comparison(v or 0,prev[k] or 0),"year_comparison":comparison(v or 0,year_prev[k] or 0)} for k,v in cur.items()}}

def finance_series(db,start,end,location_id=None,granularity="day"):
    start,end=bounds(start,end); data=[]
    d=start
    while d<=end:
        rev=float(db.scalar(select(func.coalesce(func.sum(Session.revenue),0)).where(*session_filters(d,d,location_id),Session.status=="completed")) or 0)
        expq=select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.expense_date==d,Expense.voided==False)
        if location_id:expq=expq.where(Expense.location_id==location_id)
        exp=float(db.scalar(expq) or 0); data.append({"date":str(d),"revenue":round(rev,2),"expenses":round(exp,2),"profit":round(rev-exp,2)}); d+=timedelta(days=1)
    if granularity=="month":
        grouped={}
        for p in data:
            key=p["date"][:7];g=grouped.setdefault(key,{"date":key,"revenue":0.0,"expenses":0.0,"profit":0.0})
            for metric in ("revenue","expenses","profit"):g[metric]+=p[metric]
        return [{k:round(v,2) if isinstance(v,float) else v for k,v in p.items()} for p in grouped.values()]
    return data

def demand(db,start,end,location_id=None,room_id=None,metric="reservations"):
    rows=db.execute(select(Session).where(*session_filters(*bounds(start,end),location_id,room_id),Session.status=="completed")).scalars().all(); agg=defaultdict(float)
    for r in rows: agg[(r.starts_at.weekday(),r.starts_at.hour)]+=r.revenue if metric=="revenue" else r.customers if metric=="customers" else 1
    return [{"weekday":d,"hour":h,"value":round(v,2)} for (d,h),v in sorted(agg.items())]

def forecast(db,metric="revenue",horizon=8):
    today=date.today(); start=today-timedelta(weeks=104); vals=[]; labels=[]
    for i in range(104):
        a=start+timedelta(weeks=i); b=a+timedelta(days=6); labels.append(str(a));
        value=db.scalar(select(func.coalesce(func.sum(Session.revenue if metric=="revenue" else 1),0)).where(*session_filters(a,b),Session.status=="completed")); vals.append(float(value or 0))
    pred=seasonal_naive(vals,horizon,52)
    return {"metric":metric,"model":"seasonal_naive_52w","trained_at":datetime.utcnow().isoformat(),"history":[{"date":d,"value":round(v,2)} for d,v in zip(labels,vals)],"forecast":[] if pred is None else [{"week":i+1,"value":v} for i,v in enumerate(pred)],"metrics":backtest_seasonal(vals,52),"status":"insufficient_data" if pred is None else "ready"}

def forecast_hybrid(db,metric="revenue"):
    base=forecast(db,metric,1);values=[x["value"] for x in base["history"]]
    if len(values)<56:return {**base,"status":"insufficient_data"}
    last_year=values[-52];recent=sum(values[-4:])/4;prior=sum(values[-8:-4])/4 or 1;trend=recent/prior;seasonal=last_year;median_recent=sorted(values[-8:])[4];hybrid=.55*(seasonal*trend)+.45*median_recent
    candidates={"seasonal_naive":seasonal,"recent_median":median_recent,"year_plus_trend":hybrid}
    spread=max(abs(hybrid-seasonal),abs(hybrid-median_recent),hybrid*.08)
    return {**base,"model":"hybrid_year_trend","next_week":round(hybrid,2),"last_year_reference":round(last_year,2),"recent_trend_percent":round((trend-1)*100,2),"expected_range":[round(max(0,hybrid-spread),2),round(hybrid+spread,2)],"candidates":{k:round(v,2) for k,v in candidates.items()}}

def review_topics(db,start=None,end=None,location_id=None,room_id=None):
    q=select(Review)
    if start:q=q.where(Review.review_date>=start)
    if end:q=q.where(Review.review_date<=end)
    if location_id:q=q.where(Review.location_id==location_id)
    if room_id:q=q.where(Review.room_id==room_id)
    rows=db.scalars(q).all();agg={}
    for r in rows:
        for t in json.loads(r.topics):
            a=agg.setdefault(t["aspect"],{"aspect":t["aspect"],"positive":0,"neutral":0,"negative":0,"reviews":[]});key={"positivo":"positive","neutral":"neutral","negativo":"negative"}[t["sentiment"]];a[key]+=1;a["reviews"].append({"id":r.id,"date":r.review_date,"text":r.original_text,"sentiment":t["sentiment"],"location_id":r.location_id,"room_id":r.room_id})
    return sorted(({**v,"mentions":v["positive"]+v["neutral"]+v["negative"]} for v in agg.values()),key=lambda x:x["mentions"],reverse=True)

def rooms(db,start=None,end=None):
    out=[]
    for room in db.scalars(select(Room).where(Room.active==True)).all():
        x=kpis(db,start,end,room_id=room.id)["kpis"]; reviews=db.scalars(select(Review).where(Review.room_id==room.id)).all(); rating=sum(r.rating or 0 for r in reviews)/len(reviews) if reviews else 0; sentiment=sum(100 if r.sentiment=="positivo" else 0 if r.sentiment=="negativo" else 50 for r in reviews)/len(reviews) if reviews else 50
        health=room_health(x["revenue"]["comparison"]["percent"] or 0,x["occupancy"]["value"] or 0,rating,sentiment,4)
        out.append({"id":room.id,"name":room.name,"location_id":room.location_id,"metrics":{k:v["value"] for k,v in x.items()},"rating":round(rating,2),"health":health})
    return out

def insights(db,start=None,end=None):
    data=kpis(db,start,end); rev=data["kpis"]["revenue"]; demand_rows=demand(db,start,end); top=max(demand_rows,key=lambda x:x["value"],default=None); out=[]
    if rev["comparison"]["percent"] is not None: out.append({"type":"HECHO","title":"Evolución de ingresos","message":f"Los ingresos variaron un {rev['comparison']['percent']:+.1f}% frente al periodo comparable.","evidence":rev})
    if top: out.append({"type":"INTERPRETACIÓN","title":"Concentración de demanda","message":f"La mayor concentración observada aparece el día {top['weekday']} a las {top['hour']}:00.","evidence":top})
    if rev["comparison"]["percent"] is not None and rev["comparison"]["percent"]<-10: out.append({"type":"RECOMENDACIÓN","title":"Revisar la caída","message":"Revisar disponibilidad y acciones comerciales en las franjas con mayor descenso; no se atribuye causalidad.","evidence":rev})
    return out

def anomalies(db):
    series=finance_series(db,date.today()-timedelta(days=120),date.today()); return robust_anomalies([{"date":p["date"],"value":p["revenue"],"series":"revenue"} for p in series])
