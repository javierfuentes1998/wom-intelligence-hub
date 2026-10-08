import json,re,uuid,unicodedata,queue,threading
from collections import defaultdict
from datetime import date,timedelta
from sqlalchemy import func,select
from sqlalchemy.orm import Session as DB
from .config import settings
from .gm import gm_summary,rate_for
from .models import Alert,Expense,GameMaster,Review,Room,Session
from .service import forecast_hybrid,kpis,review_topics
from .predictions import business_prediction
from .room_detail import room_detail
from .demand_map import demand_map

WRITE_WORDS=re.compile(r"\b(delete|update|insert|drop|alter|borra|elimina|modifica|crea|añade)\b",re.I)
TOOLS={"revenue","finance","reservations","expenses","players","sessions","occupancy","average_ticket","demand","rooms","locations","game_masters","cancellations","reviews","forecast","alerts"};HISTORY=defaultdict(list)
ROOM_ALIASES={"sotano":"SOTANO","hammer":"HAMMER","reliquias":"RELIQUIAS","yucatan":"YUCATAN","magia":"MAGIA","basilisco":"BASILISCO","semillas":"SEMILLAS","pesadillas":"PESADILLAS_II"}
LOCATION_ALIASES={"los angeles":"LOS_ANGELES","la florida":"LA_FLORIDA","republica argentina":"LA_FLORIDA","altozano":"ALTOZANO","orihuela":"ORIHUELA"}
LOCATION_NAMES={"LA_FLORIDA":"República Argentina / La Florida","ALTOZANO":"Altozano","LOS_ANGELES":"Los Ángeles","ORIHUELA":"Orihuela"}
def _fold(value):return unicodedata.normalize("NFKD",value.lower()).encode("ascii","ignore").decode()
def _scope_name(db,context):
    if context.get("room_id"):
        room=db.get(Room,context["room_id"]);return room.name if room else context["room_id"]
    if context.get("location_id"):return LOCATION_NAMES.get(context["location_id"],context["location_id"])
    return "WOM"
def _period_name(start,end):
    months=("enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre")
    if start.day==1 and start.year==end.year and start.month==end.month:return f"{months[start.month-1]} de {start.year}"
    return f"del {start:%d/%m/%Y} al {end:%d/%m/%Y}"
def _money(value,decimals=2):
    return f"{value:,.{decimals}f}".replace(",","X").replace(".",",").replace("X",".")+" €"
def chart_spec(kind,labels,datasets):
    if kind not in {"bar","line","table"}:raise ValueError("Tipo de gráfico no permitido")
    if len(labels)>60:raise ValueError("Demasiados puntos")
    return {"type":kind,"labels":[str(x) for x in labels],"datasets":[{"label":str(d["label"])[:80],"values":[float(v) for v in d["values"]]} for d in datasets]}
def _intent(question):
    q=question.lower();n=_fold(question)
    if "sala" in n and any(x in n for x in ("mas reserva","mayor reserva","factur","ingres","ocupacion")):return "rooms"
    if ("local" in n or "sede" in n) and any(x in n for x in ("mas reserva","factur","ingres","ocupacion")):return "locations"
    if "tarifa" in q or re.search(r"cu[aá]nto cobra",q):return "game_masters"
    if any(re.search(rf"\b{re.escape(name)}\b",q) for name in ("ivarn","hestiax","aster","bruma","cirox","daliax","elar","fionex","galoz","lumera")):return "game_masters"
    if "alquiler" in q or "gasto" in q or "nómina" in q or "nomina" in q:return "expenses"
    if any(x in n for x in ROOM_ALIASES):return "rooms"
    if any(x in n for x in LOCATION_ALIASES):return "locations"
    if any(x in q for x in ("beneficio","margen","rentabilidad","resultado económico","resultado economico")):return "finance"
    if "previsi" in q or "próxima" in q or "proxima" in q:return "forecast"
    if "preocupar" in q or "importante" in q or "alerta" in q:return "alerts"
    if "cancel" in q:return "cancellations"
    if "ticket" in q:return "average_ticket"
    if "ocupaci" in q:return "occupancy"
    if "jugador" in q or "cliente" in q:return "players"
    if "sesion" in n:return "sessions"
    if "reserva" in q:return "reservations"
    if "reseña" in q or "resena" in n or "valoraci" in q or "fortaleza" in q or "problema" in q:return "reviews"
    if "demanda" in q or "concentraci" in q:return "demand"
    if "game master" in q or re.search(r"\bgm\b",q):return "game_masters"
    if "local" in q or "sede" in q:return "locations"
    if "sala" in q:return "rooms"
    if any(x in q for x in ("sótano","sotano","yucatán","yucatan","hammer","reliquias","magia","basilisco","semillas","pesadillas")):return "rooms"
    if any(x in q for x in ("factur","ingres","venta","ticket")):return "revenue"
    return None
def _tool(db,tool,question,context):
    today=date.today();start=today-timedelta(days=today.weekday());end=start+timedelta(days=6)
    if context.get("start") and context.get("end"):start,end=date.fromisoformat(context["start"]),date.fromisoformat(context["end"])
    if "anterior" in question.lower():days=(end-start).days+1;end=start-timedelta(days=1);start=end-timedelta(days=days-1)
    scope=_scope_name(db,context);period_name=_period_name(start,end)
    if tool=="revenue":
        if "año pasado" in question.lower():start,end=start.replace(year=start.year-1),end.replace(year=end.year-1)
        x=kpis(db,start,end,context.get("location_id"),context.get("room_id"))["kpis"]["revenue"];comparison=x["comparison"]["percent"];change=f", un {abs(comparison):.1f} % {'más' if comparison>0 else 'menos'} que en el periodo anterior" if comparison is not None else "";return {"summary":f"Según Inicio y Finanzas, {scope} registró {_money(x['value'])} de ingresos en {period_name}{change}. Datos DEMO.","value":x["value"],"comparison":x["comparison"],"period":[str(start),str(end)]}
    if tool=="finance":
        metrics=kpis(db,start,end,context.get("location_id"),context.get("room_id"))["kpis"]
        profit=metrics["profit"]["value"];margin=metrics["margin"]["value"]
        return {"summary":f"Según Finanzas, {scope} obtuvo {_money(profit)} de beneficio y un margen del {margin:.1f} % en {period_name}. Datos DEMO.","profit":profit,"margin":margin,"revenue":metrics["revenue"]["value"],"expenses":metrics["expenses"]["value"],"period":[str(start),str(end)]}
    if tool=="expenses":
        q=select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.voided==False,Expense.expense_date>=start,Expense.expense_date<=end)
        if "alquiler" in question.lower():q=q.where(Expense.concept.ilike("%alquiler%"))
        if "nómina" in question.lower() or "nomina" in question.lower():q=q.where(Expense.concept.ilike("%nóminas%"))
        normalized=unicodedata.normalize("NFKD",question.lower()).encode("ascii","ignore").decode()
        location=next((loc for terms,loc in [(("los angeles",),"LOS_ANGELES"),(("la florida","republica argentina"),"LA_FLORIDA"),(("altozano",),"ALTOZANO"),(("orihuela",),"ORIHUELA")] if any(term in normalized for term in terms)),context.get("location_id"))
        if location:q=q.where(Expense.location_id==location)
        value=float(db.scalar(q) or 0);return {"summary":f"Según Finanzas, los gastos de {scope} suman {_money(value)} en {period_name}. Datos DEMO.","value":value,"period":[str(start),str(end)]}
    if tool=="reservations":
        x=kpis(db,start,end,context.get("location_id"),context.get("room_id"))["kpis"]["reservations"];return {"summary":f"{scope} registró {x['value']} reservas en {period_name}. Datos DEMO.","value":x["value"],"comparison":x["comparison"],"period":[str(start),str(end)]}
    if tool in ("players","occupancy","average_ticket"):
        key={"players":"customers","occupancy":"occupancy","average_ticket":"average_ticket"}[tool];metric=kpis(db,start,end,context.get("location_id"),context.get("room_id"))["kpis"][key];labels={"players":"jugadores","occupancy":"ocupación","average_ticket":"ticket medio por jugador"};value=metric["value"];shown=f"{value:,.2f} €" if tool=="average_ticket" and value is not None else f"{value:.2f} %" if tool=="occupancy" and value is not None else str(value if value is not None else "no disponible");return {"summary":f"Según el Hub, {scope} registró {shown} de {labels[tool]} en {period_name}. Datos DEMO.","value":value,"comparison":metric["comparison"],"period":[str(start),str(end)]}
    if tool=="sessions":
        filters=[func.date(Session.starts_at)>=start,func.date(Session.starts_at)<=end]
        if context.get("room_id"):filters.append(Session.room_id==context["room_id"])
        elif context.get("location_id"):filters.append(Session.room_id.in_(select(Room.id).where(Room.location_id==context["location_id"])))
        value=db.scalar(select(func.count()).select_from(Session).where(*filters)) or 0;return {"summary":f"{scope} tiene {value} sesiones registradas en {period_name}. Datos DEMO.","value":value,"period":[str(start),str(end)]}
    if tool=="demand":
        mapped=demand_map(db,start,end,context.get("location_id"),context.get("room_id"));cells=[c for row in mapped["weekly"] for c in row["cells"] if c["available"]];top=max(cells,key=lambda c:c["reservations"],default=None);days=("lunes","martes","miércoles","jueves","viernes","sábado","domingo");summary=f"La mayor concentración de {scope} aparece los {days[top['weekday']]} a las {top['hour']}, con {top['reservations']} reservas de {top['available']} sesiones ofrecidas." if top else "No hay demanda disponible para ese ámbito y periodo.";return {"summary":summary+" Datos DEMO.","top":top,"period":[str(start),str(end)]}
    if tool in ("rooms","locations"):
        normalized=_fold(question)
        room_id=next((rid for alias,rid in ROOM_ALIASES.items() if alias in normalized),context.get("room_id"))
        if tool=="rooms" and room_id:
            detail=room_detail(db,room_id,start,end);m=detail["kpis"];return {"summary":f"Según Salas, {detail['room']['name']} registró {m['reservations']} reservas, {m['players']} jugadores, {m['revenue']:,.2f} € de ingresos y una ocupación del {m['occupancy']:.2f} % en {period_name}. Datos DEMO.","room":detail["room"],"metrics":m,"period":[str(start),str(end)]}
        asks_rooms=any(x in normalized for x in ("que salas hay","cuales son las salas","salas tiene","lista de salas"))
        if asks_rooms:
            location=next((loc for term,loc in [("los angeles","LOS_ANGELES"),("la florida","LA_FLORIDA"),("republica argentina","LA_FLORIDA"),("altozano","ALTOZANO"),("orihuela","ORIHUELA")] if term in normalized),context.get("location_id"))
            q=select(Room).where(Room.active==True)
            if location:q=q.where(Room.location_id==location)
            room_rows=db.scalars(q.order_by(Room.name)).all();names=[x.name for x in room_rows]
            scope={"LA_FLORIDA":"La Florida","ALTOZANO":"Altozano","LOS_ANGELES":"Los Ángeles","ORIHUELA":"Orihuela"}.get(location,"WOM")
            return {"summary":f"{scope} tiene {len(names)} salas: {', '.join(names)}.","count":len(names),"rooms":names,"location_id":location}
        if tool=="locations" and "mensual" in question.lower():
            labels=[f"{start.year}-{m:02}" for m in range(1,13)];wanted=[("ALTOZANO","Altozano"),("LA_FLORIDA","República Argentina")];sets=[]
            for loc,label in wanted:
                values=[]
                for month in range(1,13):
                    value=db.scalar(select(func.coalesce(func.sum(Session.revenue),0)).join(Room,Room.id==Session.room_id).where(Room.location_id==loc,Session.status=="completed",func.strftime("%Y-%m",Session.starts_at)==f"{start.year}-{month:02}"));values.append(float(value or 0))
                sets.append({"label":label,"values":values})
            spec=chart_spec("line",labels,sets);return {"summary":"Comparativa mensual calculada desde las sesiones del backend.","period":start.year,"chart":spec}
        metric="occupancy" if "ocupaci" in normalized else "reservations" if "reserva" in normalized else "revenue";entities=db.scalars(select(Room).where(Room.active==True)).all() if tool=="rooms" else db.execute(select(Room.location_id).distinct()).scalars().all();data=[]
        for entity in entities:
            entity_id=entity.id if tool=="rooms" else entity;values=kpis(db,start,end,room_id=entity_id if tool=="rooms" else None,location_id=entity_id if tool=="locations" else None)["kpis"];data.append({"name":entity.name if tool=="rooms" else LOCATION_NAMES.get(entity_id,entity_id),"id":entity_id,"revenue":values["revenue"]["value"],"reservations":values["reservations"]["value"],"occupancy":values["occupancy"]["value"]})
        data.sort(key=lambda x:x[metric] if x[metric] is not None else -1,reverse=True)
        if tool=="rooms":
            for item in data:item["trend"]=kpis(db,start,end,room_id=next((r.id for r in db.scalars(select(Room)).all() if r.name==item["name"]),None))["kpis"]["revenue"]["comparison"]["percent"]
            if "crec" in question.lower():data.sort(key=lambda x:x["trend"] if x["trend"] is not None else -999,reverse=True)
        unit="€" if metric=="revenue" else "%" if metric=="occupancy" else "reservas";return {"summary":f"Según {'Salas' if tool=='rooms' else 'Locales'}, {data[0]['name']} lidera con {data[0][metric]:,.2f} {unit} en {period_name}. Datos DEMO." if data else "No hay datos en el periodo.","ranking":data,"metric":metric}
    if tool=="game_masters":
        normalize=lambda value:unicodedata.normalize("NFKD",value.lower()).encode("ascii","ignore").decode()
        qn=normalize(question);matches=[]
        for gm in db.scalars(select(GameMaster).where(GameMaster.active==True)).all():
            name=normalize(gm.display_name)
            if re.search(rf"\b{re.escape(name)}\b",qn):matches.append(gm)
        if matches:
            gm=max(matches,key=lambda item:len(item.display_name));x=gm_summary(db,gm.id,start,end);pay="Tarifa no configurada" if x["estimated_pay"] is None else f"{x['estimated_pay']:,.2f} €"
            if "sesión" in question.lower() or "sesion" in question.lower() or "tarifa" in question.lower() or "cobra" in question.lower():
                amount=rate_for(db,gm.home_location_id,start);return {"summary":f"La tarifa de {gm.display_name} es {amount:,.2f} € por sesión GM.","game_master":gm.display_name,"rate":amount,"unit":"sesión GM","period":[str(start),str(end)]}
            return {"summary":f"{gm.display_name} ha realizado {x['sessions']} sesiones DEMO y su remuneración estimada es {pay}.","game_master":gm.display_name,"sessions":x["sessions"],"estimated_pay":x["estimated_pay"],"pay_complete":x["pay_complete"],"details":x["details"][:20],"period":[str(start),str(end)]}
        normalized=unicodedata.normalize("NFKD",question.lower()).encode("ascii","ignore").decode()
        location=next((loc for term,loc in [("los angeles","LOS_ANGELES"),("la florida","LA_FLORIDA"),("republica argentina","LA_FLORIDA"),("altozano","ALTOZANO"),("orihuela","ORIHUELA")] if term in normalized),None)
        if location:
            amount=rate_for(db,location,start);return {"summary":f"La tarifa configurada es {amount:,.2f} € por sesión GM.","location_id":location,"rate":amount,"unit":"sesión GM","period":[str(start),str(end)]}
        rows=[]
        for gm in db.scalars(select(GameMaster).where(GameMaster.active==True)).all():
            x=gm_summary(db,gm.id,start,end);rows.append({"name":gm.display_name,"sessions":x["sessions"]})
        rows.sort(key=lambda x:x["sessions"],reverse=True);return {"summary":f"{rows[0]['name']} acumula más sesiones ({rows[0]['sessions']})." if rows else "Sin datos.","ranking":rows}
    if tool=="cancellations":
        rows=db.execute(select(Room.name,func.sum(func.iif(Session.status=="cancelled",1,0)),func.count(Session.id)).join(Session,Session.room_id==Room.id).where(func.date(Session.starts_at)>=start,func.date(Session.starts_at)<=end,Session.status.in_(("completed","cancelled"))).group_by(Room.id)).all();data=[{"name":n,"rate":round(c/t*100,1) if t else 0,"sample":t} for n,c,t in rows];data.sort(key=lambda x:x["rate"],reverse=True);return {"summary":f"La mayor tasa es {data[0]['name']}: {data[0]['rate']}% (n={data[0]['sample']})." if data else "Sin reservas comparables.","ranking":data}
    if tool=="reviews":
        q=select(Review).where(Review.review_date>=start,Review.review_date<=end)
        if context.get("location_id"):q=q.where(Review.location_id==context["location_id"])
        if context.get("room_id"):q=q.where(Review.room_id==context["room_id"])
        rows=db.scalars(q).all();ratings=[x.rating for x in rows if x.rating is not None];positive=sum(x.sentiment=="positivo" for x in rows);negative=sum(x.sentiment=="negativo" for x in rows);topics=review_topics(db,start,end,context.get("location_id"),context.get("room_id"));strength=max(topics,key=lambda x:x["positive"],default=None);problem=max(topics,key=lambda x:x["negative"],default=None);rating=sum(ratings)/len(ratings) if ratings else None;summary=f"Según Análisis de reseñas, hay {len(rows)} reseñas"+(f" con una valoración media de {rating:.2f}/5" if rating is not None else "")+f": {positive} positivas y {negative} negativas."+(f" La fortaleza más mencionada es {strength['aspect']}." if strength and strength['positive'] else "")+(f" El principal problema es {problem['aspect']}." if problem and problem['negative'] else "")+" Datos DEMO.";return {"summary":summary,"reviews":len(rows),"average_rating":rating,"positive":positive,"negative":negative,"topics":topics[:5]}
    if tool=="alerts":
        rows=db.scalars(select(Alert).where(Alert.status=="ACTIVE").order_by(Alert.relevance_score.desc()).limit(5)).all();return {"summary":f"La principal señal es: {rows[0].title} (relevancia {rows[0].relevance_score:.0f}/100)." if rows else "No hay alertas activas.","alerts":[{"title":x.title,"severity":x.severity,"deviation":x.deviation,"relevance":x.relevance_score} for x in rows]}
    mode="month" if "mes" in question.lower() else "week";x=business_prediction(db,mode,context.get("location_id"),context.get("room_id"));revenue=x.get("prediction",{}).get("revenue",{}).get("display");reservations=x.get("prediction",{}).get("reservations",{}).get("display");target=x.get("target",{}).get("label");return {"summary":f"Según Predicciones, para {target} se estiman {reservations} reservas y {revenue:,.0f} € de ingresos. Método: {x.get('method',{}).get('rule')}. Datos DEMO." if revenue is not None else x.get("message","No hay histórico suficiente para calcular la previsión."),"forecast":x}
def _gemini(prompt):
    if not settings.gemini_api_key:return None
    from google import genai
    client=genai.Client(api_key=settings.gemini_api_key)
    try:return client.models.generate_content(model=settings.gemini_model,contents=prompt).text
    finally:client.close()
def _gemini_with_timeout(prompt):
    result=queue.Queue(maxsize=1)
    def run():
        try:result.put((True,_gemini(prompt)))
        except Exception as exc:result.put((False,exc))
    threading.Thread(target=run,daemon=True).start()
    try:ok,value=result.get(timeout=max(1,min(settings.llm_timeout_seconds,8)))
    except queue.Empty:raise TimeoutError("El proveedor de lenguaje no respondió a tiempo")
    if not ok:raise value
    return value
def answer(db:DB,question:str,context=None,session_id=None,use_llm=False):
    if WRITE_WORDS.search(question):return {"status":"refused","answer":"El asistente es de solo lectura y no puede modificar datos."}
    context=context or {};session_id=session_id or str(uuid.uuid4());normalized=_fold(question)
    if re.search(r"\bpor que\b",normalized) and any(x in normalized for x in ("baj","sub","ingres","reserva","ocupacion")):return {"status":"clarification","answer":"Puedo cuantificar la variación y comparar reservas, ocupación o ticket medio, pero los datos actuales no permiten atribuir una causa con certeza.","session_id":session_id,"provider":"local"}
    if "mejor sala" in normalized:return {"status":"clarification","answer":"¿Quieres comparar las salas por ingresos, reservas u ocupación?","session_id":session_id,"provider":"local"}
    if "2035" in normalized:return {"status":"unsupported","answer":"No existe una predicción validada para 2035. Puedo consultar la previsión de la próxima semana o del próximo mes.","session_id":session_id,"provider":"local"}
    people=[_fold(x.display_name) for x in db.scalars(select(GameMaster).where(GameMaster.active==True)).all()]
    personal_name=any(re.search(rf"\b{re.escape(name)}\b",normalized) for name in people)
    if personal_name and (any(x in normalized for x in ("sueldo","salario","nomina")) or ("cobra" in normalized and "sesion" not in normalized and "tarifa" not in normalized)):return {"status":"refused","answer":"No dispongo de nóminas ni salarios personales. Las tarifas GM y la nómina contable son conceptos distintos.","session_id":session_id,"provider":"local"}
    tool=_intent(question);provider="local"
    if not tool and HISTORY[session_id]:tool=HISTORY[session_id][-1]["tool"]
    if tool is None and use_llm and settings.gemini_api_key:
        try:
            raw=_gemini_with_timeout('Devuelve SOLO JSON {"tool":"..."}. Herramientas permitidas: '+", ".join(sorted(TOOLS))+'. Pregunta: '+question);candidate=json.loads(raw.strip().removeprefix("```json").removesuffix("```")).get("tool")
            if candidate in TOOLS and tool is None:tool=candidate
        except Exception:pass
    if not tool:return {"status":"unsupported","answer":"No tengo ese dato disponible todavía. Puedo ayudarte con ingresos, gastos, reservas, jugadores, ocupación, salas, locales, reseñas, predicciones y alertas.","session_id":session_id,"provider":"local"}
    if HISTORY[session_id] and ("sesiones" in question.lower() or "gráfico" in question.lower() or "grafico" in question.lower()) and HISTORY[session_id][-1]["tool"]==tool:data=HISTORY[session_id][-1]["data"]
    else:data=_tool(db,tool,question,context)
    response=data["summary"]
    # Core intents return deterministic wording. Gemini is used only to classify
    # otherwise unsupported language, never to calculate or rewrite numbers.
    HISTORY[session_id].append({"question":question,"tool":tool,"data":data});HISTORY[session_id]=HISTORY[session_id][-8:]
    result={"status":"ok","answer":response,"tool":"get_revenue" if tool=="revenue" else tool,"data":data,"provider":provider,"session_id":session_id,"context":context}
    if data.get("chart"):result["chart"]=data["chart"]
    return result
