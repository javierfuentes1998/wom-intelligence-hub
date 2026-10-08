import json
from datetime import date

from sqlalchemy import func, select

from app.config import settings
from app.demo_reviews import LOCATIONS, generate_demo_reviews
from app.models import Location, ProcessedReview, RawReview, Review, Session
from app.review_service import DEMO_SOURCE, GOOGLE_SOURCE, active_source, build_gold
from tests.test_reviews_v270 import add_dimensions


def corpus(db,count=120,seed=2701):
    if not db.scalar(select(func.count()).select_from(Location)):add_dimensions(db)
    return generate_demo_reviews(db,count=count,seed=seed,reset=True)


def test_demo_corpus_is_reproducible(db):
    corpus(db,80,2701);one=db.execute(select(RawReview.external_review_id,RawReview.content_hash,RawReview.comment).where(RawReview.source==DEMO_SOURCE).order_by(RawReview.id)).all()
    corpus(db,80,2701);two=db.execute(select(RawReview.external_review_id,RawReview.content_hash,RawReview.comment).where(RawReview.source==DEMO_SOURCE).order_by(RawReview.id)).all()
    assert one==two and len(one)==80


def test_demo_covers_four_locations_without_touching_dimensions(db):
    corpus(db,120);before=db.scalar(select(func.count()).select_from(Location));generate_demo_reviews(db,120,2701,True)
    counts=dict(db.execute(select(RawReview.wom_location_id,func.count()).where(RawReview.source==DEMO_SOURCE).group_by(RawReview.wom_location_id)).all())
    assert counts=={key:30 for key in LOCATIONS} and db.scalar(select(func.count()).select_from(Location))==before


def test_demo_contains_empty_text_languages_rooms_and_broad_aspects(db):
    corpus(db,240);gold=build_gold(db,source=DEMO_SOURCE)
    empty=db.scalar(select(func.count()).select_from(RawReview).where(RawReview.source==DEMO_SOURCE,RawReview.comment.is_(None)))
    rooms=db.scalar(select(func.count()).select_from(ProcessedReview).join(RawReview).where(RawReview.source==DEMO_SOURCE,ProcessedReview.room_id.is_not(None)))
    assert empty>0 and rooms>0 and gold["language_distribution"]["en"]>0 and gold["language_distribution"]["fr"]>0
    assert len({x["aspect"] for x in gold["topics"]})>=24


def test_mixed_reviews_preserve_opposite_aspect_sentiments(db):
    corpus(db,240)
    rows=db.scalars(select(ProcessedReview).join(RawReview).where(RawReview.source==DEMO_SOURCE)).all()
    assert any({x["sentiment"] for x in json.loads(row.aspects)} >= {"positivo","negativo"} for row in rows)


def test_people_are_entities_never_topics(db):
    corpus(db,240);rows=db.scalars(select(ProcessedReview).join(RawReview).where(RawReview.source==DEMO_SOURCE)).all();entities=[x for row in rows for x in json.loads(row.entities)]
    topics={x["aspect"] for x in build_gold(db,source=DEMO_SOURCE)["topics"]}
    assert any(x["name"]=="Lumera" and x["type"]=="known_game_master" for x in entities)
    assert any(x["name"]=="Zorik" and x["type"]=="person_candidate" for x in entities)
    assert {x["name"] for x in entities if x["type"]=="person_candidate"}=={"Zorik"}
    assert not ({"Aster","Lumera","Elar","Bruma","Zorik"}&topics) and "atencion_equipo" in topics


def test_gold_filters_recalculate_and_evidence_is_literal(db):
    corpus(db,240);all_gold=build_gold(db,source=DEMO_SOURCE);local=build_gold(db,location_id="LA_FLORIDA",source=DEMO_SOURCE);five=build_gold(db,stars=5,source=DEMO_SOURCE)
    temp=build_gold(db,aspect="temperatura",source=DEMO_SOURCE);negative=build_gold(db,sentiment="negativo",source=DEMO_SOURCE)
    assert all_gold["kpis"]["reviews"]==240 and local["kpis"]["reviews"]==60 and 0<five["kpis"]["reviews"]<240
    assert temp["topics"] and all(x["aspect"]=="temperatura" for x in temp["topics"])
    assert negative["kpis"]["reviews"]>0
    evidence=temp["topics"][0]["evidence"][0];raw=db.scalar(select(RawReview).where(RawReview.external_review_id==evidence["review_id"]))
    assert evidence["full_text"]==raw.comment and evidence["quote"] in raw.comment


def test_demo_and_google_are_never_mixed(db):
    corpus(db,40);db.add(RawReview(id="google:one",source=GOOGLE_SOURCE,external_review_id="one",google_location_id="g/1",wom_location_id="LA_FLORIDA",star_rating=5,comment="Google real",content_hash="x"*64,raw_payload="{}",active=True));db.flush()
    db.add(ProcessedReview(raw_review_id="google:one",language="es",normalized_text="google real",sentiment_label="positivo",sentiment_score=1,confidence=.8,aspects="[]",entities="[]",analysis_status="analyzed",analyzer_version="1.0.0"));db.commit()
    assert build_gold(db,source=DEMO_SOURCE)["kpis"]["reviews"]==40
    assert build_gold(db,source=GOOGLE_SOURCE)["kpis"]["reviews"]==1


def test_source_switch_is_configuration_only(monkeypatch):
    monkeypatch.setattr(settings,"reviews_source","demo");assert active_source()==DEMO_SOURCE
    monkeypatch.setattr(settings,"reviews_source","google_business_profile");assert active_source()==GOOGLE_SOURCE


def test_regeneration_does_not_contaminate_legacy_reviews_or_sessions(db):
    corpus(db,40);legacy_before=db.scalar(select(func.count()).select_from(Review));sessions_before=db.scalar(select(func.count()).select_from(Session))
    generate_demo_reviews(db,60,2702,True)
    assert db.scalar(select(func.count()).select_from(Review))==legacy_before and db.scalar(select(func.count()).select_from(Session))==sessions_before


def test_dashboard_api_uses_demo_source(client,db):
    add_dimensions(db);generate_demo_reviews(db,40,2701,True)
    body=client.get("/api/reviews/dashboard").json()
    assert body["source"]["mode"]=="demo" and body["source"]["is_demo"] is True and body["kpis"]["reviews"]==40
    assert body["source"]["google_integration"]=="prepared_pending_authorization"


def test_v271_frontend_is_transparent_and_traceable():
    js=open("frontend/reviews-v271.js",encoding="utf-8").read();html=open("frontend/index.html",encoding="utf-8").read()
    assert "DATOS DEMO" in js and "RAW → PROCESSED → GOLD" in js and "reseñas reales" not in js
    assert "Google Business Profile: preparada" in js and "reviews-v271.js" in html
