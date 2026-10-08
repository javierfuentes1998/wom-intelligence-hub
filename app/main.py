import logging, uuid, json
from datetime import date, datetime, timedelta
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .config import ROOT, settings
from .db import Base, SessionLocal, engine, get_db
from .models import Alert,DataImportRun,DataSource,Expense,ExpenseCategory,GameMaster,GameMasterRate,Location,RecurringExpensePlan,Review,ReviewLocationMap,Room,RoomSchedule,Season,Session as WorkSession
from .schemas import ChatIn,ExpenseIn, ExpenseOut, GameMasterIn, LocationIn, RecurringPlanIn, RoomIn
from .service import anomalies, demand, finance_series, forecast_hybrid, insights, kpis, review_topics, rooms
from .temporal import granularity,period_bounds,previous_year,shift_period
from .gm import gm_summary
from .chat import answer
from .connectors import CSVConnector,ExcelConnector
from .recurring import materialize
from .alerts import DETECTORS,engine_status,evaluate_alerts
from .sync import sync_source,SyncError
from .timeseries import business_timeseries
from .finance import expense_detail,finance_center,income_detail
from .room_detail import room_detail
from .demand_map import demand_map
from .demo_gm import ensure_v223_rates,migrate_demo_game_masters
from .google_reviews import GoogleBusinessProfileClient,GoogleReviewError,credentials_configured
from .review_service import GOOGLE_SOURCE,active_source,build_gold,source_config,sync_reviews
from .review_nlp import ASPECT_PATTERNS
from .predictions import business_prediction
from .data_management import history as import_history,import_selected,sources as managed_sources

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
log=logging.getLogger("wom_hub"); Base.metadata.create_all(engine)
with SessionLocal() as startup_db:migrate_demo_game_masters(startup_db);ensure_v223_rates(startup_db)
app=FastAPI(title="The Works of Madness Intelligence Hub",version="1.0.0",description="API de inteligencia empresarial. Datos DEMO identificados.")

@app.get("/api/health")
def health(): return {"status":"ok","demo":True,"assistant_configured":bool(settings.gemini_api_key),"assistant_provider":"gemini" if settings.gemini_api_key else "local"}
@app.get("/api/dashboard")
def dashboard(start:date|None=None,end:date|None=None,location_id:str|None=None,room_id:str|None=None,db:Session=Depends(get_db)): return kpis(db,start,end,location_id,room_id)
@app.get("/api/data-range")
def data_range(db:Session=Depends(get_db)):
    session_min,session_max=db.execute(select(func.min(func.date(WorkSession.starts_at)),func.max(func.date(WorkSession.starts_at)))).one()
    expense_min,expense_max=db.execute(select(func.min(Expense.expense_date),func.max(Expense.expense_date)).where(Expense.voided==False)).one()
    values=[date.fromisoformat(str(x)) for x in (session_min,session_max,expense_min,expense_max) if x]
    return {"min_date":min(values) if values else None,"max_date":max(values) if values else None}
@app.get("/api/finance")
def finance(start:date|None=None,end:date|None=None,location_id:str|None=None,granularity:str=Query("day",pattern="^(day|month)$"),db:Session=Depends(get_db)): return finance_series(db,start,end,location_id,granularity)
@app.get("/api/finance/center")
def finance_hub(start:date,end:date,location_id:str|None=None,room_id:str|None=None,expense_view:str=Query("accounting",pattern="^(accounting|accrued)$"),include_details:bool=True,db:Session=Depends(get_db)):return finance_center(db,start,end,location_id,room_id,expense_view,include_details)
@app.get("/api/finance/income-detail")
def finance_income_detail(start:date,end:date,location_id:str|None=None,room_id:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(50,ge=25,le=100),search:str|None=None,date_from:date|None=None,date_to:date|None=None,filter_location:str|None=None,filter_room:str|None=None,gm:str|None=None,status:str|None=None,payment:str|None=None,players_min:int|None=Query(None,ge=0),players_max:int|None=Query(None,ge=0),revenue_min:float|None=None,revenue_max:float|None=None,sort:str="date",direction:str=Query("desc",pattern="^(asc|desc)$"),db:Session=Depends(get_db)):
    try:return income_detail(db,start,end,location_id,room_id,page,page_size,search,date_from,date_to,filter_location,filter_room,gm,status,payment,players_min,players_max,revenue_min,revenue_max,sort,direction)
    except ValueError as exc:raise HTTPException(422,str(exc))
@app.get("/api/finance/expense-detail")
def finance_expense_detail(start:date,end:date,location_id:str|None=None,room_id:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(50,ge=25,le=100),search:str|None=None,date_from:date|None=None,date_to:date|None=None,concept:str|None=None,category:str|None=None,filter_location:str|None=None,filter_room:str|None=None,expense_type:str|None=None,periodicity:str|None=None,amount_min:float|None=None,amount_max:float|None=None,sort:str="date",direction:str=Query("desc",pattern="^(asc|desc)$"),db:Session=Depends(get_db)):
    try:return expense_detail(db,start,end,location_id,room_id,page,page_size,search,date_from,date_to,concept,category,filter_location,filter_room,expense_type,periodicity,amount_min,amount_max,sort,direction)
    except ValueError as exc:raise HTTPException(422,str(exc))
@app.get("/api/analytics/timeseries")
def timeseries(start_date:date,end_date:date,metrics:list[str]=Query(default=["revenue"]),granularity:str=Query("auto",pattern="^(auto|day|week|month|quarter)$"),scope_type:str=Query("company",pattern="^(company|location|room)$"),scope_id:str|None=None,expense_view:str=Query("accounting",pattern="^(accounting|accrued)$"),db:Session=Depends(get_db)):
    try:return business_timeseries(db,start_date,end_date,metrics,granularity,scope_type,scope_id,expense_view)
    except ValueError as exc:raise HTTPException(422,str(exc))
@app.get("/api/locations")
def locations(db:Session=Depends(get_db)): return [{"id":x.id,"name":x.name,"active":x.active} for x in db.scalars(select(Location)).all()]
@app.get("/api/rooms")
def room_list(start:date|None=None,end:date|None=None,db:Session=Depends(get_db)): return rooms(db,start,end)
@app.get("/api/rooms/{room_id}/detail")
def room_detail_api(room_id:str,start:date,end:date,db:Session=Depends(get_db)):
    try:return room_detail(db,room_id,start,end)
    except ValueError as exc:raise HTTPException(404,str(exc))
@app.get("/api/demand")
def demand_api(start:date|None=None,end:date|None=None,location_id:str|None=None,room_id:str|None=None,metric:str=Query("reservations",pattern="^(reservations|customers|revenue)$"),db:Session=Depends(get_db)): return demand(db,start,end,location_id,room_id,metric)
@app.get("/api/demand/map")
def demand_map_api(start:date,end:date,location_id:str|None=None,room_id:str|None=None,db:Session=Depends(get_db)):return demand_map(db,start,end,location_id,room_id)
@app.get("/api/reviews")
def reviews(db:Session=Depends(get_db)): return [{"id":r.id,"date":r.review_date,"rating":r.rating,"text":r.original_text,"sentiment":r.sentiment,"score":r.sentiment_score,"topics":r.topics} for r in db.scalars(select(Review).order_by(Review.review_date.desc()).limit(200)).all()]
@app.get("/api/review-topics")
def topics(start:date|None=None,end:date|None=None,location_id:str|None=None,room_id:str|None=None,db:Session=Depends(get_db)):return review_topics(db,start,end,location_id,room_id)
@app.get("/api/reviews/source")
def review_source(db:Session=Depends(get_db)):
    mode=active_source();x=source_config(db,mode);google=source_config(db,GOOGLE_SOURCE)
    return {"mode":mode,"provider":x.provider,"status":x.status,"is_demo":mode=="demo","account_configured":bool(google.account_id),"credentials_configured":credentials_configured(),"scope":google.oauth_scope,"google_status":google.status,"last_attempt_at":x.last_attempt_at,"last_success_at":x.last_success_at,"last_error":x.last_error,"counts":{"received":x.received_count,"new":x.new_count,"modified":x.modified_count,"unchanged":x.unchanged_count,"errors":x.error_count}}
@app.get("/api/reviews/location-mappings")
def review_mappings(db:Session=Depends(get_db)):
    return [{"google_location_id":x.google_location_id,"google_name":x.google_name,"google_address":x.google_address,"wom_location_id":x.wom_location_id,"confirmed":x.confirmed,"active":x.active} for x in db.scalars(select(ReviewLocationMap).order_by(ReviewLocationMap.google_name)).all()]
@app.patch("/api/reviews/location-mappings/{google_location_id:path}")
def update_review_mapping(google_location_id:str,body:dict,db:Session=Depends(get_db)):
    x=db.get(ReviewLocationMap,google_location_id)
    if not x:raise HTTPException(404,"Mapeo de ubicación no encontrado")
    location_id=body.get("wom_location_id")
    if location_id and not db.get(Location,location_id):raise HTTPException(422,"Local WOM no válido")
    x.wom_location_id=location_id;x.confirmed=bool(body.get("confirmed",False));x.updated_at=datetime.utcnow();db.commit()
    return {"google_location_id":x.google_location_id,"wom_location_id":x.wom_location_id,"confirmed":x.confirmed}
@app.post("/api/reviews/sync")
def sync_google_reviews(db:Session=Depends(get_db)):
    if not credentials_configured():raise HTTPException(409,"ACCIÓN HUMANA NECESARIA: autorizar Google Business Profile antes de sincronizar datos reales")
    try:return sync_reviews(db,GoogleBusinessProfileClient())
    except (GoogleReviewError,ValueError) as exc:raise HTTPException(exc.status_code if isinstance(exc,GoogleReviewError) and exc.status_code else 502,str(exc))
@app.get("/api/reviews/dashboard")
def review_dashboard(start:date|None=None,end:date|None=None,location_id:str|None=None,stars:int|None=Query(None,ge=1,le=5),sentiment:str|None=None,aspect:str|None=None,language:str|None=None,period_mode:str|None=Query(None,pattern="^(week|month|year|custom)$"),db:Session=Depends(get_db)):
    return build_gold(db,start,end,location_id,stars,sentiment,aspect,language,period_mode=period_mode)
@app.get("/api/reviews/admin-config")
def review_admin_config(db:Session=Depends(get_db)):
    mode=active_source();cfg=source_config(db,mode);google=source_config(db,GOOGLE_SOURCE)
    return {"source":{"mode":mode,"provider":cfg.provider,"status":cfg.status,"google_status":google.status,"scope":google.oauth_scope},
            "location_mapping_endpoint":"/api/reviews/location-mappings","known_people_source":"dim_game_master",
            "known_people_count":db.scalar(select(func.count()).select_from(GameMaster)) or 0,
            "taxonomy":sorted(ASPECT_PATTERNS),"confidence_threshold":settings.review_min_confidence,
            "sync_interval_minutes":settings.review_sync_interval_minutes,"analyzer_version":settings.review_analyzer_version}
@app.get("/api/forecast")
def forecast_api(metric:str=Query("revenue",pattern="^(revenue|reservations)$"),db:Session=Depends(get_db)): return forecast_hybrid(db,metric)
@app.get("/api/predictions")
def predictions_api(mode:str=Query("week",pattern="^(week|month)$"),location_id:str|None=None,room_id:str|None=None,db:Session=Depends(get_db)):
    try:return business_prediction(db,mode,location_id,room_id)
    except ValueError as exc:raise HTTPException(422,str(exc))
@app.get("/api/anomalies")
def anomalies_api(db:Session=Depends(get_db)): return anomalies(db)
@app.get("/api/insights")
def insights_api(start:date|None=None,end:date|None=None,db:Session=Depends(get_db)): return insights(db,start,end)
@app.get("/api/expense-categories")
def categories(db:Session=Depends(get_db)): return [{"id":x.id,"name":x.name} for x in db.scalars(select(ExpenseCategory)).all()]
@app.post("/api/expense-categories",status_code=201)
def create_category(name:str,db:Session=Depends(get_db)):
    if db.scalar(select(ExpenseCategory).where(ExpenseCategory.name==name)): raise HTTPException(409,"La categoría ya existe")
    x=ExpenseCategory(name=name.strip()); db.add(x); db.commit(); db.refresh(x); return {"id":x.id,"name":x.name}
@app.get("/api/expenses",response_model=list[ExpenseOut])
def expenses(db:Session=Depends(get_db)): return db.scalars(select(Expense).order_by(Expense.expense_date.desc()).limit(500)).all()
@app.post("/api/expenses",response_model=ExpenseOut,status_code=201)
def create_expense(body:ExpenseIn,db:Session=Depends(get_db)):
    if body.recurrence_key and db.scalar(select(Expense).where(Expense.recurrence_key==body.recurrence_key,Expense.voided==False)): raise HTTPException(409,"Gasto recurrente duplicado")
    if body.room_id:
        room=db.get(Room,body.room_id)
        if not room or (body.location_id and room.location_id!=body.location_id): raise HTTPException(422,"Sala/local incoherentes")
    x=Expense(id=str(uuid.uuid4()),**body.model_dump()); db.add(x); db.commit(); db.refresh(x); log.info("expense_created id=%s",x.id); return x
@app.put("/api/expenses/{expense_id}",response_model=ExpenseOut)
def edit_expense(expense_id:str,body:ExpenseIn,db:Session=Depends(get_db)):
    x=db.get(Expense,expense_id)
    if not x: raise HTTPException(404,"Gasto no encontrado")
    for k,v in body.model_dump().items(): setattr(x,k,v)
    db.commit(); db.refresh(x); return x
@app.delete("/api/expenses/{expense_id}",status_code=204)
def void_expense(expense_id:str,db:Session=Depends(get_db)):
    x=db.get(Expense,expense_id)
    if not x: raise HTTPException(404,"Gasto no encontrado")
    x.voided=True; db.commit()
@app.get("/api/period")
def period(mode:str=Query("week",pattern="^(week|month|year|custom)$"),anchor:date=date.today(),start:date|None=None,end:date|None=None):
    a,b=period_bounds(mode,anchor,start,end);p1,p2=shift_period(mode,a,b,-1);y1,y2=previous_year(a,b);return {"start":a,"end":b,"previous":{"start":p1,"end":p2},"previous_year":{"start":y1,"end":y2},"granularity":granularity(mode)}
@app.get("/api/sessions")
def sessions(start:date,end:date,location_id:str|None=None,room_id:str|None=None,db:Session=Depends(get_db)):
    q=select(WorkSession,Room).join(Room,Room.id==WorkSession.room_id).where(WorkSession.starts_at>=start,WorkSession.starts_at<end+timedelta(days=1),WorkSession.status!="available")
    if location_id:q=q.where(Room.location_id==location_id)
    if room_id:q=q.where(Room.id==room_id)
    return [{"id":s.id,"date":s.starts_at.date(),"time":s.starts_at.strftime("%H:%M"),"concept":r.name,"room_id":r.id,"location_id":r.location_id,"players":s.customers,"revenue":s.revenue,"gm_id":s.game_master_id,"second_gm_id":s.second_game_master_id,"status":s.status,"discount":s.discount,"refund":s.refund} for s,r in db.execute(q.order_by(WorkSession.starts_at.desc())).all()]
@app.get("/api/game-masters")
def game_masters(db:Session=Depends(get_db)):return [{"id":x.id,"display_name":x.display_name,"home_location_id":x.home_location_id,"active":x.active,"source_system":x.source_system} for x in db.scalars(select(GameMaster).order_by(GameMaster.display_name)).all()]
@app.get("/api/game-masters/{gm_id}/summary")
def gm_metrics(gm_id:str,start:date,end:date,location_id:str|None=None,room_id:str|None=None,db:Session=Depends(get_db)):
    if not db.get(GameMaster,gm_id):raise HTTPException(404,"Game Master no encontrado")
    if room_id:
        room=db.get(Room,room_id)
        if not room:raise HTTPException(404,"Sala no encontrada")
        if location_id and room.location_id!=location_id:raise HTTPException(422,"La sala no pertenece al local seleccionado")
    return gm_summary(db,gm_id,start,end,location_id,room_id)
@app.get("/api/alerts")
def alerts(status:str|None=None,refresh:bool=False,location_id:str|None=None,room_id:str|None=None,event_type:str|None=None,source_module:str|None=None,db:Session=Depends(get_db)):
    if refresh:evaluate_alerts(db)
    q=select(Alert)
    if status:q=q.where(Alert.status==status.upper())
    rows=[]
    for x in db.scalars(q.order_by(Alert.relevance_score.desc(),Alert.created_at.desc())).all():
        evidence=json.loads(x.evidence);alert_room=evidence.get("room_id");room=db.get(Room,alert_room) if alert_room else None
        if room_id and alert_room!=room_id:continue
        if location_id and (not room or room.location_id!=location_id):continue
        if event_type and evidence.get("event_type")!=event_type:continue
        if source_module and evidence.get("source_module")!=source_module:continue
        rows.append({"id":x.id,"category":x.category,"severity":x.severity,"title":x.title,"explanation":x.explanation,"evidence":evidence,"created_at":x.created_at,"seen":x.seen,"status":x.status,"detected_at":x.detected_at,"last_evaluated_at":x.last_evaluated_at,"resolved_at":x.resolved_at,"current_value":x.current_value,"baseline_value":x.baseline_value,"deviation":x.deviation,"evidence_strength":x.evidence_strength,"relevance_score":x.relevance_score})
    return rows
@app.patch("/api/alerts/{alert_id}/seen")
def mark_seen(alert_id:str,db:Session=Depends(get_db)):
    x=db.get(Alert,alert_id)
    if not x:raise HTTPException(404,"Alerta no encontrada")
    x.seen=True;db.commit();return {"id":x.id,"seen":True}
@app.post("/api/alerts/evaluate")
def evaluate_now(db:Session=Depends(get_db)):
    evaluate_alerts(db,trigger="manual_api");return engine_status(db)
@app.get("/api/alerts/engine/status")
def alert_engine_status(db:Session=Depends(get_db)):return engine_status(db)
@app.get("/api/alerts/detectors")
def alert_detectors():return [{"id":key,**value} for key,value in DETECTORS.items()]
@app.get("/api/data-sources")
def data_sources(db:Session=Depends(get_db)):
    now=datetime.utcnow();return [{"id":x.id,"name":x.name,"type":x.source_type,"status":x.status,"last_sync":x.last_sync_at,"records":x.record_count,"errors":x.error_count,"expected_refresh_minutes":x.expected_refresh_minutes,"freshness":"sin sincronizar" if not x.last_sync_at else "al día" if (now-x.last_sync_at).total_seconds()<=x.expected_refresh_minutes*60 else "retrasada","last_error":x.last_error,"strategy":x.strategy} for x in db.scalars(select(DataSource)).all()]
@app.get("/api/data-management/sources")
def management_sources():return managed_sources()
@app.post("/api/data-management/import")
def management_import(body:dict,db:Session=Depends(get_db)):
    try:return import_selected(db,str(body.get("source_id","")),list(body.get("datasets") or []))
    except ValueError as exc:raise HTTPException(422,str(exc))
@app.get("/api/data-management/history")
def management_history(limit:int=20,db:Session=Depends(get_db)):return import_history(db,min(limit,100))
@app.post("/api/data-sources/{source_id}/sync")
def sync_api(source_id:str,records:list[dict],db:Session=Depends(get_db)):
    try:return sync_source(db,source_id,records)
    except SyncError as exc:raise HTTPException(404,str(exc))
@app.get("/api/admin/rates")
def rates(db:Session=Depends(get_db)):return [{"id":x.id,"location_id":x.location_id,"room_id":x.room_id,"amount":x.amount,"type":x.rate_type,"valid_from":x.valid_from,"valid_to":x.valid_to,"active":x.active} for x in db.scalars(select(GameMasterRate)).all()]
@app.get("/api/admin/schedules")
def schedules(db:Session=Depends(get_db)):return [{"id":x.id,"room_id":x.room_id,"weekday":x.weekday,"start_time":x.start_time,"valid_from":x.valid_from,"valid_to":x.valid_to,"active":x.active} for x in db.scalars(select(RoomSchedule)).all()]
@app.get("/api/admin/seasons")
def seasons(db:Session=Depends(get_db)):return [{"id":x.id,"name":x.name,"start":x.start_date,"end":x.end_date,"active":x.active} for x in db.scalars(select(Season)).all()]
@app.post("/api/admin/locations",status_code=201)
def add_location(body:LocationIn,db:Session=Depends(get_db)):
    if db.get(Location,body.id):raise HTTPException(409,"ID existente")
    x=Location(**body.model_dump(),source_system="MANUAL");db.add(x);db.commit();return body
@app.post("/api/admin/rooms",status_code=201)
def add_room(body:RoomIn,db:Session=Depends(get_db)):
    if not db.get(Location,body.location_id):raise HTTPException(422,"Local inexistente")
    x=Room(**body.model_dump(),source_system="MANUAL");db.add(x);db.commit();return body
@app.post("/api/admin/game-masters",status_code=201)
def add_gm(body:GameMasterIn,db:Session=Depends(get_db)):
    if db.get(GameMaster,body.id):raise HTTPException(409,"ID existente")
    x=GameMaster(**body.model_dump(),source_system="MANUAL");db.add(x);db.commit();return body
@app.get("/api/recurring-expenses")
def recurring(db:Session=Depends(get_db)):return [{"id":x.id,"concept":x.concept,"amount":x.amount,"periodicity":x.periodicity,"valid_from":x.valid_from,"valid_to":x.valid_to,"active":x.active} for x in db.scalars(select(RecurringExpensePlan)).all()]
@app.post("/api/recurring-expenses",status_code=201)
def add_recurring(body:RecurringPlanIn,db:Session=Depends(get_db)):
    x=RecurringExpensePlan(id=str(uuid.uuid4()),**body.model_dump());db.add(x);db.commit();return {"id":x.id,**body.model_dump()}
@app.post("/api/recurring-expenses/{plan_id}/materialize")
def materialize_recurring(plan_id:str,start:date,end:date,db:Session=Depends(get_db)):
    x=db.get(RecurringExpensePlan,plan_id)
    if not x:raise HTTPException(404,"Plan no encontrado")
    rows=materialize(db,x,start,end);return {"created":len(rows),"idempotent":True}
@app.post("/api/import/preview")
async def import_preview(file:UploadFile=File(...)):
    suffix=Path(file.filename or "").suffix.lower();data=await file.read()
    if len(data)>10_000_000:raise HTTPException(413,"Archivo demasiado grande")
    try:
        if suffix==".csv":return CSVConnector().preview(data)
        if suffix in (".xlsx",".xls"):
            import io
            return ExcelConnector().preview(io.BytesIO(data))
    except Exception as exc:raise HTTPException(422,f"Archivo inválido: {exc}")
    raise HTTPException(415,"Formato permitido: CSV o Excel")
@app.post("/api/assistant/query")
def assistant(body:ChatIn,db:Session=Depends(get_db)):return answer(db,body.question,body.context,body.session_id,use_llm=bool(body.context))

static=ROOT/"frontend"; app.mount("/assets",StaticFiles(directory=static),name="assets")
@app.get("/{path:path}",include_in_schema=False)
def spa(path:str): return FileResponse(static/"index.html")
