import json
from datetime import datetime

import httpx
import pytest

from app.google_reviews import GoogleBusinessProfileClient, GoogleReviewError
from app.models import GameMaster, Location, ProcessedReview, RawReview, ReviewLocationMap
from app.review_nlp import analyze_review
from app.review_service import GOOGLE_SOURCE,build_gold, discover_locations, suggest_location, sync_reviews


LOCATIONS={"LA_FLORIDA":"República Argentina / La Florida","ALTOZANO":"Altozano","LOS_ANGELES":"Los Ángeles","ORIHUELA":"Orihuela"}


def add_dimensions(db):
    for key,name in LOCATIONS.items():db.add(Location(id=key,name=name,active=True,source_system="DEMO"))
    db.add(GameMaster(id="JAVI",display_name="Lumera",active=True,source_system="DEMO"));db.commit()


def test_nlp_aspects_negation_people_rooms_and_no_text():
    result=analyze_review("Lumera fue genial, pero hacía mucho calor en El Sótano.",4,["Lumera"])
    assert {x["aspect"] for x in result["aspects"]}>={"atencion_equipo","temperatura"}
    assert {x["sentiment"] for x in result["aspects"] if x["aspect"]=="temperatura"}=={"negativo"}
    assert result["entities"][0]["type"]=="known_game_master" and result["room_id"]=="SOTANO"
    assert "javi_espin" not in {x["aspect"] for x in result["aspects"]}
    assert analyze_review(None,5)["aspects"]==[] and analyze_review(None,5)["sentiment_label"] is None


def test_nlp_unknown_person_is_entity_not_topic_and_detects_discrepancy():
    result=analyze_review("Nos atendió Zorik y fue excelente.",1,[])
    assert any(x["name"]=="Zorik" and x["type"]=="person_candidate" for x in result["entities"])
    assert result["star_text_discrepancy"] is True
    assert all(x["aspect"]!="Zorik" for x in result["aspects"])


@pytest.mark.parametrize("text,stars,expected_sentiment,expected_aspects",[
    ("La experiencia fue genial",5,"muy_positivo",{"experiencia_general"}),
    ("La experiencia fue terrible",1,"muy_negativo",{"experiencia_general"}),
    ("Ambientación genial pero demasiado calor",3,"mixto_neutral",{"ambientacion","temperatura"}),
    ("Los puzles fueron excelentes y la historia genial",5,"muy_positivo",{"puzzles","historia"}),
    ("La experiencia no fue genial",2,"muy_negativo",{"experiencia_general"}),
    ("Hammer Killer fue una experiencia increíble",5,"muy_positivo",{"experiencia_general"}),
    ("The escape room was great",5,"muy_positivo",{"experiencia_general"}),
    ("Los actores fueron excelentes",5,"muy_positivo",{"actores"}),
    ("Era demasiado fácil",2,"muy_negativo",{"dificultad"}),
    ("El precio fue caro",2,"muy_negativo",{"precio"}),
    ("La web de reserva fue terrible",1,"muy_negativo",{"reserva"}),
    ("Sí, claro, esperar 40 minutos fue genial",3,"mixto_neutral",{"espera"}),
    ("Estuvo bien",3,"mixto_neutral",set()),
])
def test_manual_gold_standard(text,stars,expected_sentiment,expected_aspects):
    result=analyze_review(text,stars)
    assert result["sentiment_label"]==expected_sentiment
    assert {x["aspect"] for x in result["aspects"]}>=expected_aspects


def test_location_suggestions_cover_exactly_four_businesses():
    assert suggest_location("WOM República Argentina - La Florida")=="LA_FLORIDA"
    assert suggest_location("WOM Altozano")=="ALTOZANO"
    assert suggest_location("The Works of Madness Los Ángeles")=="LOS_ANGELES"
    assert suggest_location("WOM Orihuela")=="ORIHUELA"
    assert suggest_location("Otro negocio") is None


def test_google_client_paginates_and_retries_without_exposing_token():
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        if len(calls)==1:return httpx.Response(429,json={"error":"quota"})
        token=request.url.params.get("pageToken")
        return httpx.Response(200,json={"reviews":[{"reviewId":"2" if token else "1"}],**({"nextPageToken":"next"} if not token else {})})
    client=httpx.Client(transport=httpx.MockTransport(handler))
    rows=GoogleBusinessProfileClient(client,lambda:"secret-token",max_attempts=3).list_reviews("accounts/a/locations/l")
    assert [x["reviewId"] for x in rows]==["1","2"] and len(calls)==3
    assert all("secret-token" not in url for url in calls)


def test_google_client_does_not_retry_authorization_errors():
    calls=[]
    client=httpx.Client(transport=httpx.MockTransport(lambda request:(calls.append(1) or httpx.Response(403,json={}))))
    try:GoogleBusinessProfileClient(client,lambda:"x").list_accounts()
    except GoogleReviewError as exc:assert exc.status_code==403
    else:assert False
    assert len(calls)==1


class FakeGoogle:
    def __init__(self,reviews):self.reviews=reviews
    def list_accounts(self):return [{"name":"accounts/1"}]
    def list_locations(self,account):
        return [{"name":f"accounts/1/locations/{key}","title":name,"storefrontAddress":{"locality":"Alicante"}} for key,name in LOCATIONS.items()]
    def list_reviews(self,location):return list(self.reviews.get(location,[]))


def review(review_id="r1",comment="La ambientación fue excelente",stars="FIVE",update="2026-09-02T10:00:00Z"):
    return {"reviewId":review_id,"reviewer":{"displayName":"Cliente"},"starRating":stars,"comment":comment,
            "createTime":"2026-09-01T10:00:00Z","updateTime":update}


def prepare_mappings(db):
    for key,name in LOCATIONS.items():db.add(ReviewLocationMap(google_location_id=f"accounts/1/locations/{key}",wom_location_id=key,google_name=name,confirmed=True,active=True))
    db.commit()


def test_discovery_preserves_ids_and_requires_confirmation(db):
    add_dimensions(db);rows=discover_locations(db,FakeGoogle({}),"accounts/1")
    assert len(rows)==4 and {x.wom_location_id for x in rows}==set(LOCATIONS)
    assert not any(x.confirmed for x in rows)


def test_sync_is_incremental_idempotent_and_reprocesses_changes(db):
    add_dimensions(db);prepare_mappings(db);location="accounts/1/locations/LA_FLORIDA";fake=FakeGoogle({location:[review()]})
    one=sync_reviews(db,fake);assert one["created"]==1 and one["modified"]==0
    raw=db.scalars(__import__('sqlalchemy').select(RawReview)).one();processed=db.get(ProcessedReview,raw.id);first=processed.analyzed_at
    two=sync_reviews(db,fake);assert two["unchanged"]==1 and db.get(ProcessedReview,raw.id).analyzed_at==first
    fake.reviews[location]=[review(comment="La ambientación fue terrible",update="2026-09-03T10:00:00Z")]
    three=sync_reviews(db,fake);assert three["modified"]==1 and db.get(RawReview,raw.id).comment.endswith("terrible")


def test_disappeared_review_is_retained_and_marked_inactive(db):
    add_dimensions(db);prepare_mappings(db);location="accounts/1/locations/ALTOZANO";fake=FakeGoogle({location:[review()]})
    sync_reviews(db,fake);fake.reviews[location]=[];sync_reviews(db,fake)
    raw=db.scalars(__import__('sqlalchemy').select(RawReview)).one();assert raw.active is False


def test_gold_uses_only_real_pipeline_and_protects_reviewer_privacy(db):
    add_dimensions(db);prepare_mappings(db);location="accounts/1/locations/LOS_ANGELES"
    sync_reviews(db,FakeGoogle({location:[review(comment="Zorik fue excelente y la ambientación genial")]}))
    gold=build_gold(db,source=GOOGLE_SOURCE)
    assert gold["kpis"]["reviews"]==1 and gold["source"]["mapped_locations"]==4
    assert gold["denominators"]["aspects"].startswith("menciones")
    assert gold["timeline"] and "recommendations" in gold and len(gold["limitations"])>=8
    serialized=json.dumps(gold,ensure_ascii=False);assert "Cliente" not in serialized and "ambientación" in serialized


def test_api_pending_authorization_and_empty_real_dashboard(client,monkeypatch):
    import app.google_reviews as google_reviews
    monkeypatch.setattr(google_reviews.settings,"google_business_access_token",None)
    monkeypatch.setattr(google_reviews.settings,"google_business_client_id",None)
    monkeypatch.setattr(google_reviews.settings,"reviews_source","google_business_profile")
    response=client.get("/api/reviews/dashboard");assert response.status_code==200
    body=response.json();assert body["kpis"]["reviews"]==0 and body["source"]["status"]=="PENDING_AUTHORIZATION"
    sync=client.post("/api/reviews/sync");assert sync.status_code==409 and "ACCIÓN HUMANA NECESARIA" in sync.json()["detail"]
    admin=client.get("/api/reviews/admin-config");assert admin.status_code==200 and "atencion_equipo" in admin.json()["taxonomy"]


def test_frontend_names_real_module_and_keeps_demo_out_of_empty_state():
    js=open("frontend/app.js",encoding="utf-8").read()
    assert "['reviews','Análisis de reseñas']" in js
    assert "No se muestran datos DEMO como si fueran reales" in js
    assert "reviewer_display_name" not in js
