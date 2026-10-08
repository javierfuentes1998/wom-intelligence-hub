from collections import defaultdict
from datetime import date,datetime,timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from .models import Expense,ExpenseCategory,GameMaster,Location,Room,Session
from .service import kpis
from .timeseries import business_timeseries

INCOME_SORTS={"date":lambda x:(x["date"],x["time"]),"time":lambda x:x["time"],"concept":lambda x:x["concept"].casefold(),"room":lambda x:x["concept"].casefold(),"location":lambda x:x["location_id"],"players":lambda x:x["players"],"revenue":lambda x:x["revenue"],"gm":lambda x:x["gm"].casefold(),"status":lambda x:x["status"],"payment_method":lambda x:x["payment_method"] or ""}
EXPENSE_SORTS={"date":lambda x:x["date"],"concept":lambda x:x["concept"].casefold(),"category":lambda x:x["category"].casefold(),"location":lambda x:x["location_id"] or "","room":lambda x:x["room_id"] or "","amount":lambda x:x["amount"],"type":lambda x:x["type"],"periodicity":lambda x:x["periodicity"] or ""}

def _page(rows,total,page,page_size,sort,direction,options):
    start=(page-1)*page_size
    return {"items":rows[start:start+page_size],"total":total,"filtered_total":len(rows),"page":page,"page_size":page_size,"pages":max(1,(len(rows)+page_size-1)//page_size),"sort":sort,"direction":direction,"options":options}

def income_detail(db,start,end,location_id=None,room_id=None,page=1,page_size=50,search=None,date_from=None,date_to=None,filter_location=None,filter_room=None,gm=None,status=None,payment=None,players_min=None,players_max=None,revenue_min=None,revenue_max=None,sort="date",direction="desc"):
    if sort not in INCOME_SORTS:raise ValueError("Ordenación de ingresos no permitida")
    if date_from and date_to and date_from>date_to:raise ValueError("El rango de fechas no es válido")
    if players_min is not None and players_max is not None and players_min>players_max:raise ValueError("El rango de jugadores no es válido")
    if revenue_min is not None and revenue_max is not None and revenue_min>revenue_max:raise ValueError("El rango de ingresos no es válido")
    base=[]
    for s,r in _scope_sessions(db,start,end,location_id,room_id):
        first=db.get(GameMaster,s.game_master_id) if s.game_master_id else None;second=db.get(GameMaster,s.second_game_master_id) if s.second_game_master_id else None
        base.append({"id":s.id,"date":s.starts_at.date(),"time":s.starts_at.strftime("%H:%M"),"concept":r.name,"room_id":r.id,"location_id":r.location_id,"players":s.customers,"revenue":s.revenue,"gm":first.display_name if first else "Sin asignación","second_gm":second.display_name if second else None,"status":s.status,"payment_method":s.payment_method})
    options={"rooms":sorted({(x["room_id"],x["concept"]) for x in base}),"locations":sorted({x["location_id"] for x in base}),"game_masters":sorted({x["gm"] for x in base}|{x["second_gm"] for x in base if x["second_gm"]}),"statuses":sorted({x["status"] for x in base}),"payments":sorted({x["payment_method"] for x in base if x["payment_method"]})}
    rows=base;needle=(search or "").casefold().strip()
    if needle:rows=[x for x in rows if needle in " ".join(str(x[k] or "") for k in ("concept","location_id","gm","second_gm","status","payment_method")).casefold()]
    if date_from:rows=[x for x in rows if x["date"]>=date_from]
    if date_to:rows=[x for x in rows if x["date"]<=date_to]
    if filter_location:rows=[x for x in rows if x["location_id"]==filter_location]
    if filter_room:rows=[x for x in rows if x["room_id"]==filter_room]
    if gm:rows=[x for x in rows if gm in (x["gm"],x["second_gm"])]
    if status:rows=[x for x in rows if x["status"]==status]
    if payment:rows=[x for x in rows if x["payment_method"]==payment]
    if players_min is not None:rows=[x for x in rows if x["players"]>=players_min]
    if players_max is not None:rows=[x for x in rows if x["players"]<=players_max]
    if revenue_min is not None:rows=[x for x in rows if x["revenue"]>=revenue_min]
    if revenue_max is not None:rows=[x for x in rows if x["revenue"]<=revenue_max]
    rows.sort(key=INCOME_SORTS[sort],reverse=direction=="desc")
    return _page(rows,len(base),page,page_size,sort,direction,options)

def expense_detail(db,start,end,location_id=None,room_id=None,page=1,page_size=50,search=None,date_from=None,date_to=None,concept=None,category=None,filter_location=None,filter_room=None,expense_type=None,periodicity=None,amount_min=None,amount_max=None,sort="date",direction="desc"):
    if sort not in EXPENSE_SORTS:raise ValueError("Ordenación de gastos no permitida")
    if date_from and date_to and date_from>date_to:raise ValueError("El rango de fechas no es válido")
    if amount_min is not None and amount_max is not None and amount_min>amount_max:raise ValueError("El rango de importes no es válido")
    base=[{"id":x.id,"date":x.expense_date,"concept":x.concept,"category":c.name,"location_id":x.location_id,"room_id":x.room_id,"amount":x.amount,"type":"Recurrente" if x.recurring else "Puntual","periodicity":"Mensual" if x.periodicity in {"monthly","mensual"} else x.periodicity} for x,c in _scope_expenses(db,start,end,location_id,room_id)]
    options={"categories":sorted({x["category"] for x in base}),"locations":sorted({x["location_id"] for x in base if x["location_id"]}),"rooms":sorted({x["room_id"] for x in base if x["room_id"]}),"types":sorted({x["type"] for x in base}),"periodicities":sorted({x["periodicity"] for x in base if x["periodicity"]})}
    rows=base;needle=(search or "").casefold().strip()
    if needle:rows=[x for x in rows if needle in " ".join(str(x[k] or "") for k in ("concept","category","location_id","room_id","type","periodicity")).casefold()]
    if date_from:rows=[x for x in rows if x["date"]>=date_from]
    if date_to:rows=[x for x in rows if x["date"]<=date_to]
    if concept:rows=[x for x in rows if concept.casefold() in x["concept"].casefold()]
    if category:rows=[x for x in rows if x["category"]==category]
    if filter_location:rows=[x for x in rows if x["location_id"]==filter_location]
    if filter_room:rows=[x for x in rows if x["room_id"]==filter_room]
    if expense_type:rows=[x for x in rows if x["type"]==expense_type]
    if periodicity:rows=[x for x in rows if x["periodicity"]==periodicity]
    if amount_min is not None:rows=[x for x in rows if x["amount"]>=amount_min]
    if amount_max is not None:rows=[x for x in rows if x["amount"]<=amount_max]
    rows.sort(key=EXPENSE_SORTS[sort],reverse=direction=="desc")
    return _page(rows,len(base),page,page_size,sort,direction,options)

def _scope_sessions(db,start,end,location_id=None,room_id=None):
    q=select(Session,Room).join(Room,Room.id==Session.room_id).where(Session.starts_at>=datetime.combine(start,datetime.min.time()),Session.starts_at<datetime.combine(end+timedelta(days=1),datetime.min.time()),Session.status!="available")
    if location_id:q=q.where(Room.location_id==location_id)
    if room_id:q=q.where(Room.id==room_id)
    return db.execute(q.order_by(Session.starts_at.desc())).all()

def _scope_expenses(db,start,end,location_id=None,room_id=None):
    q=select(Expense,ExpenseCategory).join(ExpenseCategory,ExpenseCategory.id==Expense.category_id).where(Expense.expense_date>=start,Expense.expense_date<=end,Expense.voided==False)
    if location_id:q=q.where(Expense.location_id==location_id)
    if room_id:q=q.where(Expense.room_id==room_id)
    return db.execute(q.order_by(Expense.expense_date.desc(),Expense.amount.desc())).all()

def finance_center(db:DB,start:date,end:date,location_id=None,room_id=None,expense_view="accounting",include_details=True):
    summary=kpis(db,start,end,location_id,room_id)
    timeseries=business_timeseries(db,start,end,["revenue","expenses","profit"],"auto","room" if room_id else "location" if location_id else "company",room_id or location_id,expense_view)
    coverage_days=[]
    if expense_view=="accrued" and timeseries["granularity"]=="day":
        for point in timeseries["series"]:
            result=round(point["values"]["revenue"]-point["values"]["expenses"],2)
            point["analytical_result"]=result;point["costs_covered"]=result>=0
            coverage_days.append({"date":point["date"],"result":result,"costs_covered":result>=0})
    expenses=_scope_expenses(db,start,end,location_id,room_id);expense_total=sum(x.amount for x,_ in expenses)
    if room_id and not expenses:
        for key in ("expenses","profit","margin"):
            summary["kpis"][key]["value"]=None
    categories=defaultdict(float);recurring=0.0
    for x,c in expenses:categories[c.name]+=x.amount;recurring+=x.amount if x.recurring else 0
    breakdown=[{"category":name,"amount":round(amount,2),"percent":round(amount/expense_total*100,2) if expense_total else None} for name,amount in sorted(categories.items(),key=lambda item:item[1],reverse=True)]
    income=[]
    for s,r in _scope_sessions(db,start,end,location_id,room_id):
        gm=db.get(GameMaster,s.game_master_id) if s.game_master_id else None;gm2=db.get(GameMaster,s.second_game_master_id) if s.second_game_master_id else None
        income.append({"id":s.id,"date":s.starts_at.date(),"time":s.starts_at.strftime("%H:%M"),"concept":r.name,"room_id":r.id,"location_id":r.location_id,"players":s.customers,"revenue":s.revenue,"gm":gm.display_name if gm else "Sin asignación","second_gm":gm2.display_name if gm2 else None,"status":s.status,"discount":s.discount,"refund":s.refund,"payment_method":s.payment_method})
    expense_detail=[{"id":x.id,"date":x.expense_date,"concept":x.concept,"category":c.name,"location_id":x.location_id,"room_id":x.room_id,"amount":x.amount,"type":"Recurrente" if x.recurring else "Puntual","periodicity":"Mensual" if x.periodicity in {"monthly","mensual"} else x.periodicity,"notes":x.notes} for x,c in expenses]
    locations=[];unassigned=sum(x.amount for x,_ in expenses if x.location_id is None)
    location_query=select(Location).where(Location.active==True)
    if location_id:
        location_query=location_query.where(Location.id==location_id)
    elif room_id:
        selected_room=db.get(Room,room_id)
        if selected_room:
            location_query=location_query.where(Location.id==selected_room.location_id)
    for location in db.scalars(location_query).all():
        x=kpis(db,start,end,location_id=location.id)["kpis"];revenue=x["revenue"]["value"];cost=x["expenses"]["value"];result=revenue-cost
        locations.append({"id":location.id,"name":location.name,"revenue":revenue,"expenses":cost,"result":round(result,2),"margin":round(result/revenue*100,2) if revenue else None,"comparison":x["revenue"]["comparison"]["percent"]})
    room_rows=[]
    room_query=select(Room).where(Room.active==True)
    if location_id:
        room_query=room_query.where(Room.location_id==location_id)
    if room_id:
        room_query=room_query.where(Room.id==room_id)
    for room in db.scalars(room_query).all():
        x=kpis(db,start,end,room_id=room.id)["kpis"];direct=sum(e.amount for e,_ in _scope_expenses(db,start,end,room_id=room.id));has_direct=any(e.room_id==room.id for e,_ in expenses)
        room_rows.append({"id":room.id,"name":room.name,"location_id":room.location_id,"revenue":x["revenue"]["value"],"reservations":x["reservations"]["value"],"customers":x["customers"]["value"],"average_ticket":x["average_ticket"]["value"],"direct_costs":round(direct,2) if has_direct else None,"contribution":round(x["revenue"]["value"]-direct,2) if has_direct else None,"shared_costs_assigned":False})
    coverage={"days":coverage_days,"covered_days":sum(x["costs_covered"] for x in coverage_days),"total_days":len(coverage_days),"coverage_percent":round(sum(x["costs_covered"] for x in coverage_days)/len(coverage_days)*100,1) if coverage_days else None,"definition":"Resultado periodificado = ingresos diarios - gastos periodificados diarios"}
    return {"period":{"start":start,"end":end},"summary":summary,"timeseries":timeseries,"daily_cost_coverage":coverage,"expense_breakdown":breakdown,"expense_mix":{"recurring":round(recurring,2),"one_off":round(expense_total-recurring,2),"total":round(expense_total,2)},"locations":locations,"unassigned_costs":round(unassigned,2),"rooms":room_rows,"income_count":len(income),"expense_count":len(expense_detail),"income_detail":income if include_details else [],"expense_detail":expense_detail if include_details else []}
