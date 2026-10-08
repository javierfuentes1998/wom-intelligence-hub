"""RAW -> PROCESSED -> GOLD pipeline for real Google reviews."""
from __future__ import annotations

import json
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .google_reviews import credentials_configured
from .models import (GameMaster, ProcessedReview, RawReview, ReviewGoldSnapshot,
                     ReviewLocationMap, ReviewSourceConfig, ReviewSyncRun)
from .review_nlp import analyze_review, content_hash

GOOGLE_SOURCE_ID = "google-business-profile"
GOOGLE_SOURCE = "google_business_profile"
DEMO_SOURCE_ID = "reviews-demo"
DEMO_SOURCE = "demo"
STAR_VALUES = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
LOCATION_HINTS = {
    "LA_FLORIDA": ("florida", "republica argentina"), "ALTOZANO": ("altozano",),
    "LOS_ANGELES": ("angeles",), "ORIHUELA": ("orihuela",),
}


def _fold(value: str | None) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(c)).casefold()


def active_source() -> str:
    value=(settings.reviews_source or DEMO_SOURCE).strip().lower()
    if value not in {DEMO_SOURCE,GOOGLE_SOURCE}:raise ValueError("WOM_REVIEWS_SOURCE debe ser demo o google_business_profile")
    return value


def source_config(db: Session, source: str | None=None) -> ReviewSourceConfig:
    source=source or active_source();is_demo=source==DEMO_SOURCE
    row = db.get(ReviewSourceConfig, DEMO_SOURCE_ID if is_demo else GOOGLE_SOURCE_ID)
    if not row:
        row = ReviewSourceConfig(id=DEMO_SOURCE_ID if is_demo else GOOGLE_SOURCE_ID,provider=source,
                                 status="DEMO_READY" if is_demo else "PENDING_AUTHORIZATION",
                                 expected_refresh_minutes=settings.review_sync_interval_minutes)
        db.add(row); db.commit(); db.refresh(row)
    if not is_demo and not credentials_configured() and row.last_success_at is None:
        row.status = "PENDING_AUTHORIZATION"
    return row


def suggest_location(name: str | None, address: str | None = None) -> str | None:
    haystack = _fold(f"{name or ''} {address or ''}")
    return next((key for key, hints in LOCATION_HINTS.items() if any(hint in haystack for hint in hints)), None)


def discover_locations(db: Session, client, account_name: str) -> list[ReviewLocationMap]:
    found = []
    for item in client.list_locations(account_name):
        google_id = item.get("name")
        if not google_id: continue
        address = item.get("storefrontAddress") or {}
        address_text = ", ".join(filter(None, [address.get("addressLines", [None])[0] if address.get("addressLines") else None,
                                                address.get("locality")]))
        row = db.get(ReviewLocationMap, google_id)
        if not row:
            row = ReviewLocationMap(google_location_id=google_id, wom_location_id=suggest_location(item.get("title"), address_text),
                                    confirmed=False)
            db.add(row)
        row.google_name=item.get("title"); row.google_address=address_text; row.active=True; row.updated_at=datetime.utcnow()
        found.append(row)
    db.commit()
    return found


def _parse_time(value: str | None) -> datetime | None:
    if not value: return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _normalize_review(item: dict, mapping: ReviewLocationMap) -> dict:
    external = item.get("reviewId") or item.get("name", "").rsplit("/", 1)[-1]
    reviewer = item.get("reviewer") or {}
    reply = item.get("reviewReply") or {}
    stars = item.get("starRating")
    if isinstance(stars, str): stars = STAR_VALUES.get(stars)
    stable = {"id": external, "stars": stars, "comment": item.get("comment"), "update": item.get("updateTime"), "reply": reply}
    return {"id": f"{mapping.google_location_id}:{external}", "external_review_id": external,
            "google_location_id": mapping.google_location_id, "wom_location_id": mapping.wom_location_id,
            "reviewer_display_name": reviewer.get("displayName"), "star_rating": stars,
            "comment": item.get("comment"), "create_time": _parse_time(item.get("createTime")),
            "update_time": _parse_time(item.get("updateTime")), "reply": reply.get("comment"),
            "source_url": item.get("reviewLink"), "content_hash": content_hash(json.dumps(stable, ensure_ascii=False, sort_keys=True)),
            "raw_payload": json.dumps(item, ensure_ascii=False, sort_keys=True)}


def _process(db: Session, raw: RawReview, people: list[str]) -> None:
    row = db.get(ProcessedReview, raw.id) or ProcessedReview(raw_review_id=raw.id)
    try:
        result = analyze_review(raw.comment, raw.star_rating, people, settings.review_analyzer_version)
    except Exception as exc:
        row.analysis_status="analysis_failed";row.analysis_error=f"{type(exc).__name__}: {exc}"[:1000]
        row.analyzer_version=settings.review_analyzer_version;row.analyzed_at=datetime.utcnow();db.add(row);return
    row.language=result["language"]; row.normalized_text=result["normalized_text"]
    row.sentiment_label=result["sentiment_label"]; row.sentiment_score=result["sentiment_score"]
    row.confidence=result["confidence"]; row.aspects=json.dumps(result["aspects"], ensure_ascii=False)
    row.entities=json.dumps(result["entities"], ensure_ascii=False); row.room_id=result["room_id"]
    row.room_method=result["room_method"]; row.room_confidence=result["room_confidence"]
    row.star_text_discrepancy=result["star_text_discrepancy"]; row.analysis_status=result["analysis_status"]
    row.analyzer_method=result["analyzer_method"]; row.analyzer_version=result["analyzer_version"]
    row.analyzed_at=_parse_time(result["analyzed_at"]); row.analysis_error=None
    db.add(row)


def sync_reviews(db: Session, client) -> dict:
    cfg=source_config(db,GOOGLE_SOURCE); started=datetime.utcnow(); run=ReviewSyncRun(id=str(uuid.uuid4()), source=GOOGLE_SOURCE)
    db.add(run); cfg.last_attempt_at=started; cfg.status="SYNCING"; db.commit()
    try:
        account = cfg.account_id or settings.google_business_account_id
        if not account:
            accounts=client.list_accounts()
            if len(accounts)!=1: raise ValueError("Debe seleccionarse una cuenta de Google Business Profile")
            account=accounts[0]["name"]
        cfg.account_id=account
        discover_locations(db,client,account)
        mappings=db.scalars(select(ReviewLocationMap).where(ReviewLocationMap.active==True,ReviewLocationMap.confirmed==True,
                                                             ReviewLocationMap.wom_location_id.is_not(None))).all()
        people=[x.display_name for x in db.scalars(select(GameMaster).where(GameMaster.active==True)).all()]
        now=datetime.utcnow()
        for mapping in mappings:
            seen=set()
            for item in client.list_reviews(mapping.google_location_id):
                run.received+=1; data=_normalize_review(item,mapping); seen.add(data["id"]); raw=db.get(RawReview,data["id"])
                if raw and raw.content_hash==data["content_hash"]:
                    raw.last_seen_at=now; raw.active=True; run.unchanged+=1; continue
                if raw: run.modified+=1
                else: raw=RawReview(**data); db.add(raw); run.created+=1
                for key,value in data.items(): setattr(raw,key,value)
                raw.last_seen_at=now; raw.active=True; _process(db,raw,people)
            old=db.scalars(select(RawReview).where(RawReview.google_location_id==mapping.google_location_id,
                                                   RawReview.source==GOOGLE_SOURCE,RawReview.active==True)).all()
            for raw in old:
                if raw.id not in seen: raw.active=False
        run.status="SUCCESS"; cfg.status="CONNECTED"; cfg.last_success_at=datetime.utcnow(); cfg.last_error=None
    except Exception as exc:
        run.status="FAILED"; run.failed+=1; run.error=str(exc); cfg.status="ERROR"; cfg.last_error=str(exc)
        db.commit(); raise
    finally:
        run.finished_at=datetime.utcnow(); run.duration_ms=int((run.finished_at-started).total_seconds()*1000)
        cfg.received_count=run.received; cfg.new_count=run.created; cfg.modified_count=run.modified
        cfg.unchanged_count=run.unchanged; cfg.error_count=run.failed; db.commit()
    payload=build_gold(db,source=GOOGLE_SOURCE); snapshot=db.get(ReviewGoldSnapshot,"google:company") or ReviewGoldSnapshot(scope_key="google:company",analyzer_version=settings.review_analyzer_version,payload="{}")
    snapshot.generated_at=datetime.utcnow(); snapshot.analyzer_version=settings.review_analyzer_version; snapshot.payload=json.dumps(payload,ensure_ascii=False,default=str)
    db.add(snapshot); db.commit()
    return {"run_id":run.id,"status":run.status,"received":run.received,"created":run.created,"modified":run.modified,"unchanged":run.unchanged,"failed":run.failed}


def _strength(n: int) -> str:
    return "insuficiente" if n < 3 else "baja" if n < 8 else "moderada" if n < 20 else "sólida"


def _granularity(start: date | None, end: date | None, period_mode: str | None) -> str:
    """Business rule: week/month use days, year uses months, custom adapts."""
    if period_mode in {"week", "month"}: return "day"
    if period_mode == "year": return "month"
    days = (end - start).days + 1 if start and end else 365
    return "day" if days <= 31 else "week" if days <= 180 else "month"


def _bucket_key(value: date, granularity: str) -> str:
    if granularity == "day": return value.isoformat()
    if granularity == "week":
        monday=value-timedelta(days=value.weekday())
        return monday.isoformat()
    return value.strftime("%Y-%m")


def _bucket_keys(start: date, end: date, granularity: str) -> list[str]:
    keys=[]; cursor=start
    while cursor <= end:
        key=_bucket_key(cursor,granularity)
        if not keys or keys[-1]!=key: keys.append(key)
        cursor += timedelta(days=1)
    return keys


def build_gold(db: Session, start: date | None=None, end: date | None=None, location_id: str | None=None,
               stars: int | None=None, sentiment: str | None=None, aspect: str | None=None, language: str | None=None,
               source: str | None=None, period_mode: str | None=None) -> dict:
    source=source or active_source();cfg=source_config(db,source);is_demo=source==DEMO_SOURCE
    q=select(RawReview,ProcessedReview).join(ProcessedReview,ProcessedReview.raw_review_id==RawReview.id).where(RawReview.source==source,RawReview.active==True)
    if start:q=q.where(RawReview.create_time>=datetime.combine(start,datetime.min.time()))
    if end:q=q.where(RawReview.create_time<=datetime.combine(end,datetime.max.time()))
    if location_id:q=q.where(RawReview.wom_location_id==location_id)
    if stars:q=q.where(RawReview.star_rating==stars)
    if language:q=q.where(ProcessedReview.language==language)
    pairs=[]
    for raw,processed in db.execute(q).all():
        aspects=json.loads(processed.aspects or "[]")
        if sentiment and processed.sentiment_label!=sentiment:continue
        if aspect and not any(x["aspect"]==aspect for x in aspects):continue
        if aspect:aspects=[x for x in aspects if x["aspect"]==aspect]
        pairs.append((raw,processed,aspects))
    total=len(pairs); text_count=sum(bool(r.comment and r.comment.strip()) for r,_,_ in pairs)
    ratings=[r.star_rating for r,_,_ in pairs if r.star_rating]
    confidences=[p.confidence for _,p,_ in pairs if p.confidence is not None]
    sentiments=Counter(p.sentiment_label for _,p,_ in pairs if p.sentiment_label)
    aspect_data=defaultdict(lambda:{"positive":0,"neutral":0,"negative":0,"evidence":[]})
    for raw,processed,aspects in pairs:
        for item in aspects:
            key=item["aspect"]; tone=item["sentiment"]; aspect_data[key][{"positivo":"positive","negativo":"negative"}.get(tone,"neutral")]+=1
            aspect_data[key]["evidence"].append({"review_id":raw.external_review_id,"date":raw.create_time.date().isoformat() if raw.create_time else None,
                "location_id":raw.wom_location_id,"stars":raw.star_rating,"sentiment":tone,"quote":item["evidence"],"full_text":raw.comment})
    topics=[]
    for key,data in aspect_data.items():
        mentions=data["positive"]+data["neutral"]+data["negative"]
        topics.append({"aspect":key,"mentions":mentions,"positive":data["positive"],"neutral":data["neutral"],"negative":data["negative"],
                       "positive_rate":round(data["positive"]/mentions*100,1),"negative_rate":round(data["negative"]/mentions*100,1),
                       "sample_strength":_strength(mentions),"evidence":data["evidence"]})
    locations=[]
    for key in LOCATION_HINTS:
        subset=[x for x in pairs if x[0].wom_location_id==key]; rated=[x[0].star_rating for x in subset if x[0].star_rating]
        local_aspects=defaultdict(lambda:{"positive":0,"negative":0})
        for _,_,items in subset:
            for item in items:
                if item["sentiment"]=="positivo":local_aspects[item["aspect"]]["positive"]+=1
                elif item["sentiment"]=="negativo":local_aspects[item["aspect"]]["negative"]+=1
        best=max(local_aspects,key=lambda x:local_aspects[x]["positive"],default=None);problem=max(local_aspects,key=lambda x:local_aspects[x]["negative"],default=None)
        local_text=sum(bool(x[0].comment and x[0].comment.strip()) for x in subset)
        best_count=local_aspects[best]["positive"] if best else 0; problem_count=local_aspects[problem]["negative"] if problem else 0
        locations.append({"location_id":key,"reviews":len(subset),"reviews_with_text":local_text,"average_rating":round(sum(rated)/len(rated),2) if rated else None,
                          "sample_strength":_strength(len(subset)),"top_strength":best,"top_strength_count":local_aspects[best]["positive"] if best else 0,
                          "top_strength_rate":round(best_count/local_text*100,1) if local_text else None,
                          "top_problem":problem,"top_problem_count":problem_count,
                          "top_problem_rate":round(problem_count/local_text*100,1) if local_text else None})
    timeline=[]
    granularity=_granularity(start,end,period_mode)
    by_bucket=defaultdict(list)
    for row in pairs:
        if row[0].create_time:by_bucket[_bucket_key(row[0].create_time.date(),granularity)].append(row)
    bounds_start=start or (min((x[0].create_time.date() for x in pairs if x[0].create_time),default=None))
    bounds_end=end or (max((x[0].create_time.date() for x in pairs if x[0].create_time),default=None))
    keys=_bucket_keys(bounds_start,bounds_end,granularity) if bounds_start and bounds_end else sorted(by_bucket)
    for bucket in keys:
        rows=by_bucket.get(bucket,[]); bucket_ratings=[x[0].star_rating for x in rows if x[0].star_rating]
        analyzed=sum(bool(x[1].sentiment_label) for x in rows);positive=sum(bool(x[1].sentiment_label and "positivo" in x[1].sentiment_label) for x in rows)
        timeline.append({"period":bucket,"reviews":len(rows),"average_rating":round(sum(bucket_ratings)/len(bucket_ratings),2) if bucket_ratings else None,
                         "sentiment_denominator":analyzed,"positive_rate":round(positive/analyzed*100,1) if analyzed else None,
                         "positive":sum(bool(x[1].sentiment_label and "positivo" in x[1].sentiment_label) for x in rows),
                         "negative":sum(bool(x[1].sentiment_label and "negativo" in x[1].sentiment_label) for x in rows)})
    recommendations=[{"aspect":x["aspect"],"evidence_count":x["negative"],"priority":"revisar",
                      "explanation":f"Revisar {x['aspect'].replace('_',' ')}: {x['negative']} menciones negativas trazables."}
                     for x in sorted(topics,key=lambda item:item["negative"],reverse=True) if x["negative"]>=3 and x["sample_strength"]!="insuficiente"][:5]
    mappings=db.scalars(select(ReviewLocationMap)).all()
    positive_topics=sorted((x for x in topics if x["positive"]),key=lambda x:x["positive"],reverse=True)
    negative_topics=sorted((x for x in topics if x["negative"]),key=lambda x:x["negative"],reverse=True)
    top_positive=positive_topics[0] if positive_topics else None; top_negative=negative_topics[0] if negative_topics else None
    period_reading={
        "positive": {"aspect":top_positive["aspect"],"count":top_positive["positive"],"strength":_strength(top_positive["positive"])} if top_positive else None,
        "negative": {"aspect":top_negative["aspect"],"count":top_negative["negative"],"mentions":top_negative["mentions"],"strength":_strength(top_negative["negative"]),"recurrent":top_negative["negative"]>=3} if top_negative else None,
        "sample":{"reviews":total,"reviews_with_text":text_count,"strength":_strength(text_count)},
    }
    return {"source":{"mode":source,"is_demo":is_demo,"provider":"Dataset DEMO" if is_demo else "Google Business Profile","status":cfg.status,"last_attempt_at":cfg.last_attempt_at.isoformat() if cfg.last_attempt_at else None,
                       "last_success_at":cfg.last_success_at.isoformat() if cfg.last_success_at else None,"last_error":cfg.last_error,"credentials_configured":credentials_configured(),
                       "mapped_locations":4 if is_demo else sum(x.confirmed and bool(x.wom_location_id) for x in mappings),"target_locations":4,
                       "google_integration":"prepared_pending_authorization" if not credentials_configured() else "credentials_configured"},
            "filters":{"start":start.isoformat() if start else None,"end":end.isoformat() if end else None,"location_id":location_id,"stars":stars,"sentiment":sentiment,"aspect":aspect,"language":language},
            "kpis":{"reviews":total,"reviews_with_text":text_count,"average_rating":round(sum(ratings)/len(ratings),2) if ratings else None,
                    "positive":sum(v for k,v in sentiments.items() if k and "positivo" in k),
                    "negative":sum(v for k,v in sentiments.items() if k and "negativo" in k),"neutral_mixed":sentiments.get("mixto_neutral",0),
                    "average_confidence":round(sum(confidences)/len(confidences)*100,1) if confidences else None,"sample_strength":_strength(total)},
            "denominators":{"rating":"reseñas con estrellas","sentiment":"reseñas con texto analizado","aspects":"menciones del aspecto; una reseña puede aportar varios aspectos"},
            "sentiment_distribution":dict(sentiments),"star_distribution":dict(Counter(ratings)),
            "language_distribution":dict(Counter(p.language or "und" for _,p,_ in pairs)),"topics":sorted(topics,key=lambda x:x["mentions"],reverse=True),"locations":locations,
            "timeline":timeline,"timeline_granularity":granularity,
            "timeline_rule":"Semana y mes: día; año: mes; personalizado: día hasta 31 días, semana hasta 180 y mes para periodos mayores.",
            "period_reading":period_reading,"recommendations":recommendations,"emerging_topics":[],
            "trend":{"status":"insufficient_data" if total<16 else "available","explanation":"Se necesitan al menos 8 reseñas por tramo temporal para comparar."},
            "analyzer":{"version":settings.review_analyzer_version,"method":"reglas semánticas auditables + taxonomía empresarial","processed":total,
                         "pending":db.scalar(select(func.count()).select_from(RawReview).outerjoin(ProcessedReview).where(RawReview.source==source,ProcessedReview.raw_review_id.is_(None))) or 0,
                         "failed":db.scalar(select(func.count()).select_from(ProcessedReview).join(RawReview,RawReview.id==ProcessedReview.raw_review_id).where(RawReview.source==source,ProcessedReview.analysis_status=="analysis_failed")) or 0},
            "evidence_thresholds":{"insuficiente":"0–2 menciones","baja":"3–7 menciones","moderada":"8–19 menciones","sólida":"20 o más menciones"},
            "limitations":["El sarcasmo y la ironía pueden interpretarse mal.","Los textos muy cortos o ambiguos pueden no aportar aspectos.",
                "La detección de idioma es heurística y puede devolver 'indeterminado'.","La atribución a sala exige una mención explícita.",
                "Los nombres propios se detectan como candidatos y pueden requerir revisión.","Una muestra pequeña se etiqueta como insuficiente o baja.",
                "Las reseñas sin texto solo participan en la valoración por estrellas.","Sentimiento y aspectos son estimaciones automáticas revisables.",
                "Las estrellas y el sentimiento textual pueden discrepar sin que uno invalide al otro."]}
