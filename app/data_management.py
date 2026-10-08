"""Selective data-source abstraction for V3.0.0."""
import json,uuid
from datetime import datetime
from sqlalchemy import func,select
from sqlalchemy.orm import Session as DB
from .alerts import evaluate_alerts
from .models import DataImportRun,Expense,GameMaster,GameMasterRate,Location,Review,Room,RoomSchedule,Session

DATASETS={
 "reservations":{"label":"Reservas y sesiones","description":"Reservas, jugadores, importes y sesiones realizadas."},
 "availability":{"label":"Sesiones ofrecidas","description":"Disponibilidad de referencia para ocupación y demanda."},
 "expenses":{"label":"Gastos","description":"Movimientos necesarios para Finanzas."},
 "reviews":{"label":"Reseñas","description":"Valoraciones y comentarios para análisis NLP."},
 "game_masters":{"label":"Game Masters","description":"Identidad y estado activo de Game Masters."},
 "locations":{"label":"Locales","description":"Datos maestros de sedes."},
 "rooms":{"label":"Salas","description":"Datos maestros y capacidad de salas."},
 "gm_rates":{"label":"Tarifas de Game Masters","description":"Tarifas vigentes e históricas por ámbito."},
 "schedules":{"label":"Horarios","description":"Sesiones ofrecidas configuradas por sala y día."},
}
SOURCES={
 "demo":{"id":"demo","name":"DEMO V3","status":"Disponible","configured":True,"datasets":list(DATASETS)},
 "file":{"id":"file","name":"Archivos CSV/XLSX","status":"Disponible","configured":True,"datasets":["reservations","expenses","reviews"]},
 "wom":{"id":"wom","name":"Sistema de gestión WOM","status":"Pendiente de configurar","configured":False,"datasets":[]},
}
COUNTERS={"reservations":Session,"expenses":Expense,"reviews":Review,"game_masters":GameMaster,"locations":Location,"rooms":Room,"gm_rates":GameMasterRate,"schedules":RoomSchedule}

def sources():return [{**source,"capabilities":[{"id":key,**DATASETS[key],"available":key in source["datasets"]} for key in DATASETS]} for source in SOURCES.values()]
def _count(db,key):
    if key=="availability":return db.scalar(select(func.count()).select_from(Session).where(Session.available==True)) or 0
    return db.scalar(select(func.count()).select_from(COUNTERS[key])) or 0
def import_selected(db:DB,source_id:str,datasets:list[str]):
    source=SOURCES.get(source_id)
    if not source:raise ValueError("Fuente desconocida")
    if not source["configured"]:raise ValueError("Se requiere acceso técnico al sistema de gestión WOM para configurar esta conexión.")
    selected=list(dict.fromkeys(datasets))
    if not selected:raise ValueError("Selecciona al menos un dataset")
    invalid=[x for x in selected if x not in source["datasets"]]
    if invalid:raise ValueError(f"Datasets no disponibles en esta fuente: {', '.join(invalid)}")
    if source_id!="demo":raise ValueError("La importación de archivo requiere subir y confirmar el mapping del archivo.")
    run=DataImportRun(id=f"IMP-{uuid.uuid4().hex[:12]}",source_id=source_id,datasets=json.dumps(selected),result="{}",status="RUNNING");db.add(run);db.flush();results=[]
    try:
        for key in selected:
            processed=_count(db,key);results.append({"dataset":key,"label":DATASETS[key]["label"],"processed":processed,"new":0,"updated":0,"unchanged":processed,"errors":0})
        derived=sorted({x for key in selected for x in {"reservations":["Inicio","Finanzas","Locales","Salas","Demanda","Game Masters","Predicciones"],"availability":["Demanda","Salas"],"expenses":["Finanzas","Locales"],"reviews":["Análisis de reseñas"],"game_masters":["Game Masters"],"locations":["Locales"],"rooms":["Salas"],"gm_rates":["Game Masters"],"schedules":["Demanda"]}.get(key,[])})
        alerts=bool(set(selected)&{"reservations","availability","expenses","reviews","rooms"})
        if alerts:evaluate_alerts(db,trigger="data_import")
        payload={"run_id":run.id,"source":source["name"],"status":"COMPLETADA","datasets":results,"analyses_updated":derived,"alerts_evaluated":alerts,"stages":["RAW","VALIDATION","PROCESSED","GOLD","DEPENDENCIES","ALERT_ENGINE"]}
        run.result=json.dumps(payload,ensure_ascii=False);run.status="COMPLETADA";run.finished_at=datetime.utcnow();db.commit();return payload
    except Exception as exc:
        db.rollback();run.status="FALLIDA";run.result=json.dumps({"error":str(exc)},ensure_ascii=False);run.finished_at=datetime.utcnow();db.add(run);db.commit();raise
def history(db:DB,limit=20):
    rows=db.scalars(select(DataImportRun).order_by(DataImportRun.started_at.desc()).limit(limit)).all();return [{"id":x.id,"source_id":x.source_id,"datasets":json.loads(x.datasets),"result":json.loads(x.result),"status":x.status,"started_at":x.started_at,"finished_at":x.finished_at} for x in rows]
