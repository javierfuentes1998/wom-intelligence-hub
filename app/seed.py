import json, random, secrets, uuid
from datetime import date, datetime, time, timedelta
from pwdlib import PasswordHash
from .config import ROOT, settings
from .db import Base, SessionLocal, engine
from .models import (Alert,DataSource,Expense,ExpenseCategory,GameMaster,GameMasterRate,Location,RecurringExpensePlan,Review,Room,RoomSchedule,Season,Session,User)
from .nlp import classify
from .alerts import evaluate_alerts
from .demo_gm import DEMO_GAME_MASTERS
from .schedules import REFERENCE_SCHEDULES

LOCATIONS=[("LA_FLORIDA","WOM La Florida / República Argentina","C. República Argentina, 68","Alicante"),("ALTOZANO","WOM Altozano","C. Aureliano Ibarra, 6","Alicante"),("LOS_ANGELES","WOM Los Ángeles","C. Francisco Montero Pérez, 19","Alicante"),("ORIHUELA","Pesadillas Escape Room 2 / Orihuela","Prol. Ronda Santo Domingo, 7","Orihuela")]
ROOMS=[("SOTANO","LA_FLORIDA","El Sótano",8,"terror"),("HAMMER","LA_FLORIDA","Hammer Killer",6,"humor"),("RELIQUIAS","LA_FLORIDA","Las Reliquias de Judy",6,"gótico"),("YUCATAN","ALTOZANO","Yucatán",6,"aventura"),("MAGIA","ALTOZANO","Escuela de Magia",18,"fantasía"),("BASILISCO","ALTOZANO","El Veneno del Basilisco",12,"CluedRoom"),("SEMILLAS","LOS_ANGELES","Las Semillas de la Locura",6,"tensión"),("PESADILLAS_II","ORIHUELA","Pesadillas II",8,"terror")]
CATEGORIES=["alquiler","electricidad","agua","Internet","seguros","mantenimiento","publicidad","material","nóminas","reparaciones","licencias","otros"]
REVIEWS=["Una experiencia increíble, ambientación original e inmersión genial. El game master fue muy amable.","La sala estuvo genial pero esperamos demasiado y hacía muchísimo calor.","Puzzles divertidos, dificultad equilibrada y trato excelente.","Una prueba estaba rota y el mantenimiento fue malo.","Buen local y actores increíbles, aunque el precio nos pareció caro.","Mucho miedo, gran duración y atención fantástica."]
PROFILES={
 "SOTANO":(1.24,25.0,1.12,.055),"HAMMER":(.92,21.0,1.00,.035),"RELIQUIAS":(1.04,23.0,.86,.045),
 "YUCATAN":(1.10,20.0,1.18,.025),"MAGIA":(1.34,18.5,1.08,.03),"BASILISCO":(.74,17.0,.96,.04),
 "SEMILLAS":(.88,24.0,.78,.13),"PESADILLAS_II":(1.18,26.0,1.03,.06)}
GM_WEIGHTS={gm_id:.72+i*.09 for i,(gm_id,_,_) in enumerate(DEMO_GAME_MASTERS)}
GM_LOCATIONS={gm_id:location_id for gm_id,_,location_id in DEMO_GAME_MASTERS}

def month_iter(start,end):
    cur=start.replace(day=1)
    while cur<=end:
        yield cur;cur=(cur.replace(day=28)+timedelta(days=4)).replace(day=1)

def seed(reset=True):
    random.seed(settings.demo_seed)
    if reset:Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine);db=SessionLocal()
    try:
        for i,n,a,c in LOCATIONS:db.add(Location(id=i,name=n,address=a,city=c,source_system="DEMO"))
        for i,l,n,c,t in ROOMS:db.add(Room(id=i,location_id=l,name=n,capacity=c,experience_type=t,source_system="DEMO"))
        db.flush()
        for gm_id,name,location_id in DEMO_GAME_MASTERS:db.add(GameMaster(id=gm_id,display_name=name,home_location_id=location_id,start_date=date(2023,1,1),source_system="DEMO"))
        cats={n:ExpenseCategory(name=n) for n in CATEGORIES};db.add_all(cats.values());db.flush()
        for loc,amount in [("LA_FLORIDA",20),("ALTOZANO",18),("LOS_ANGELES",20),("ORIHUELA",25)]:db.add(GameMasterRate(location_id=loc,amount=amount,rate_type="normal",valid_from=date(2020,1,1),notes="Coste GM por sesión; independiente de nómina contable"))
        db.add(GameMasterRate(location_id="LA_FLORIDA",room_id="SOTANO",amount=26,rate_type="double",valid_from=date(2020,1,1),notes="Doble de El Sótano"))
        today=date.today();start=today-timedelta(days=1095)
        for y in range(start.year,today.year+1):
            db.add(Season(name="Navidad",start_date=date(y,12,15),end_date=date(y+1,1,7)));db.add(Season(name="Verano",start_date=date(y,7,1),end_date=date(y,8,31)))
        db.flush()
        # RoomSchedule and every consumer share the official room master schedule.
        # Do not derive a generic grid here: quarter-hour slots are meaningful.
        for room,*_ in ROOMS:
            for wd in range(7):
                for slot in REFERENCE_SCHEDULES[room]:db.add(RoomSchedule(room_id=room,weekday=wd,start_time=slot,valid_from=start,active=True))
        plans=[]
        for li,(loc,*_) in enumerate(LOCATIONS):
            for cat,amount in [("alquiler",1800+li*180),("nóminas",5200+li*350),("Internet",65),("seguros",140)]:
                p=RecurringExpensePlan(id=f"PLAN-{loc}-{cat}",concept=f"{cat.title()} {loc}",category_id=cats[cat].id,amount=amount,location_id=loc,periodicity="monthly",valid_from=start.replace(day=1));db.add(p);plans.append(p)
        sid=0
        for day_no in range((today-start).days+1):
            d=start+timedelta(days=day_no);seasonal=1.28 if (d.month==12 or (d.month==1 and d.day<=7)) else 1.12 if d.month in (7,8) else 1.0;weekend=1.55 if d.weekday()>=4 else .55
            for ri,(room_id,loc,_,cap,_) in enumerate(ROOMS):
                room_factor,price,trend,cancel_rate=PROFILES[room_id]
                hours=(11,13,16,18,20,22) if d.weekday()>=4 else (17,19,21)
                if room_id=="SOTANO" and d.weekday() in (4,5) and day_no%4==0:hours=(17,18,19,20,21)
                for hour in hours:
                    recent_progress=max(0,(d-(today-timedelta(days=150))).days/150);trend_factor=1+(trend-1)*recent_progress;anomaly=.30 if room_id=="RELIQUIAS" and 35<=(today-d).days<=48 else 1
                    sid+=1;demand=min(.98,max(.03,.43*room_factor*seasonal*weekend*trend_factor*anomaly+random.gauss(0,.075)));booked=random.random()<demand;cancelled=booked and random.random()<cancel_rate;customers=random.randint(2,cap) if booked and not cancelled else 0;discount=random.choice([0,0,0,5,10]) if booked else 0;refund=round(random.uniform(10,40),2) if cancelled and random.random()<.5 else 0;gross=customers*price if customers else 0;revenue=round(gross-discount-refund,2);double=room_id=="SOTANO" and len(hours)==5 and booked and not cancelled
                    candidates=[g for g in GM_WEIGHTS if GM_LOCATIONS[g]==loc];weights=[GM_WEIGHTS[g] for g in candidates];gm=random.choices(candidates,weights=weights,k=1)[0];second=random.choice([x for x in candidates if x!=gm]) if double else None
                    db.add(Session(id=f"S-{sid:07}",external_id=f"DEMO-{sid:07}",room_id=room_id,game_master_id=gm,second_game_master_id=second,starts_at=datetime.combine(d,time(hour)),available=True,status="cancelled" if cancelled else "completed" if booked else "available",customers=customers,revenue=revenue,price_per_person=price if customers else None,discount=discount,refund=refund,payment_method=random.choice(["card","cash","online"]),requires_double_gm=double,double_gm_source="INFERRED" if double else None,source_system="DEMO"))
            if random.random()<.18:
                loc=LOCATIONS[day_no%4][0];cat=random.choice(["electricidad","agua","mantenimiento","publicidad","material","reparaciones"]);key=f"DEMO:{d}:{loc}:{cat}";db.add(Expense(id=str(uuid.uuid5(uuid.NAMESPACE_URL,key)),concept=f"Gasto {cat}",category_id=cats[cat].id,amount=round(random.uniform(40,750),2),expense_date=d,location_id=loc,recurring=False,recurrence_key=key))
            if random.random()<.34:
                room=ROOMS[day_no%8];negative=room[0]=="SEMILLAS" and day_no%3==0;text=REVIEWS[3 if negative else day_no%len(REVIEWS)];result=classify(text);rid=f"R-{day_no:05}";db.add(Review(id=rid,external_id=f"DEMO-{rid}",review_date=d,source="DEMO",source_system="DEMO",location_id=room[1],room_id=room[0],rating=float(random.choice([1,2,3]) if negative else random.choice([4,4,5,5,5])),original_text=text,processed_text=result["processed_text"],sentiment=result["sentiment"],sentiment_score=result["score"],topics=json.dumps(result["aspects"],ensure_ascii=False)))
        for p in plans:
            for d in month_iter(p.valid_from,today):
                key=f"{p.id}:{d:%Y-%m}";db.add(Expense(id=str(uuid.uuid5(uuid.NAMESPACE_URL,key)),concept=p.concept,category_id=p.category_id,amount=p.amount,expense_date=d,location_id=p.location_id,recurring=True,periodicity="monthly",recurrence_key=key))
        for id,name,typ,status,count in [("reservations","Reservas","BookingConnector","DEMO",sid),("reviews","Reseñas","CSV/API","DEMO",0),("expenses","Gastos","Manual/CSV","DEMO",0),("game_masters","Game Masters","CSV/Excel","DEMO",10)]:db.add(DataSource(id=id,name=name,source_type=typ,status=status,record_count=count,expected_refresh_minutes=1440,strategy="incremental"))
        # A local evaluator can define WOM_DEMO_ADMIN_PASSWORD before seeding.
        # When absent, create a non-disclosed random credential rather than
        # publishing a reusable password in source code or logs.
        demo_password=settings.demo_admin_password or secrets.token_urlsafe(32)
        db.add(User(username="admin",password_hash=PasswordHash.recommended().hash(demo_password),role="admin"));db.commit();evaluate_alerts(db,today)
        for folder in (ROOT/"data"/"raw",ROOT/"data"/"processed",ROOT/"data"/"gold",ROOT/"logs",ROOT/"models"):folder.mkdir(parents=True,exist_ok=True)
        (ROOT/"data"/"DEMO_DATA.txt").write_text("DEMO V3, semilla 20260929. Sedes/salas conocidas; patrones, horarios, sesiones, GM, importes, alertas y reseñas son sintéticos. Escenarios heterogéneos reproducibles. No mezclar con datos reales.\n",encoding="utf-8")
    finally:db.close()
if __name__=="__main__":seed()
