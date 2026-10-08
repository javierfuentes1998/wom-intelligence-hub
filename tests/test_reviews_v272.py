"""V2.7.2 semantic, temporal and presentation contracts."""
from datetime import date

from app.demo_reviews import generate_demo_reviews
from app.review_nlp import ANALYZER_VERSION, analyze_review
from app.review_service import DEMO_SOURCE, GOOGLE_SOURCE, build_gold
from tests.test_reviews_v270 import add_dimensions


def corpus(db, count=120):
    add_dimensions(db); return generate_demo_reviews(db,count,2701,True)


def frontend(): return open("frontend/reviews-v271.js",encoding="utf-8").read()


def test_group_is_audited_and_renamed():
    result=analyze_review("La duración fue genial para nuestro grupo",5)
    assert ANALYZER_VERSION=="1.1.0" and any(x["aspect"]=="experiencia_grupo" for x in result["aspects"])


def test_isolated_group_words_do_not_create_aspect():
    for text in ("grupo", "Había personas", "Five players"):
        assert "experiencia_grupo" not in {x["aspect"] for x in analyze_review(text,4)["aspects"]}


def test_positive_kpi_exposes_numerator_and_denominator(db):
    corpus(db); g=build_gold(db,source=DEMO_SOURCE)
    assert g["kpis"]["positive"] <= g["kpis"]["reviews_with_text"] and " de ${den}" in frontend()


def test_negative_kpi_exposes_numerator_and_denominator(db):
    corpus(db); g=build_gold(db,source=DEMO_SOURCE)
    assert g["kpis"]["negative"] <= g["kpis"]["reviews_with_text"] and "Sentimiento negativo" in frontend()


def test_empty_reviews_are_outside_sentiment_denominator(db):
    corpus(db); g=build_gold(db,source=DEMO_SOURCE)
    assert g["kpis"]["reviews_with_text"] < g["kpis"]["reviews"]
    assert sum(g["sentiment_distribution"].values())==g["kpis"]["reviews_with_text"]


def test_confidence_is_not_a_business_kpi():
    js=frontend(); kpi=js[js.index('v271-kpis'):js.index('v271Reading')]
    assert "Confianza media" not in kpi and "confianza media" in js and "no probabilidad" in js


def test_month_uses_internal_daily_granularity(db):
    corpus(db); g=build_gold(db,date(2026,9,1),date(2026,9,30),source=DEMO_SOURCE,period_mode="month")
    assert g["timeline_granularity"]=="day" and len(g["timeline"])==30


def test_year_uses_months(db):
    corpus(db); g=build_gold(db,date(2026,1,1),date(2026,12,31),source=DEMO_SOURCE,period_mode="year")
    assert g["timeline_granularity"]=="month" and len(g["timeline"])==12


def test_custom_period_adapts_granularity(db):
    corpus(db)
    assert build_gold(db,date(2026,1,1),date(2026,1,20),source=DEMO_SOURCE,period_mode="custom")["timeline_granularity"]=="day"
    assert build_gold(db,date(2026,1,1),date(2026,4,1),source=DEMO_SOURCE,period_mode="custom")["timeline_granularity"]=="week"
    assert build_gold(db,date(2025,1,1),date(2026,1,1),source=DEMO_SOURCE,period_mode="custom")["timeline_granularity"]=="month"


def test_empty_time_buckets_are_not_interpolated(db):
    corpus(db); g=build_gold(db,date(2030,1,1),date(2030,1,7),source=DEMO_SOURCE,period_mode="week")
    assert len(g["timeline"])==7 and all(x["reviews"]==0 and x["average_rating"] is None and x["positive_rate"] is None for x in g["timeline"])


def test_single_negative_is_not_recurrent():
    js=frontend(); assert "x.negative>=3" in js and "evidencia insuficiente para considerarla recurrente" in js


def test_single_positive_is_not_consolidated():
    assert "evidencia insuficiente para considerarlo consolidado" in frontend()


def test_location_comparison_respects_period(db):
    corpus(db); a=build_gold(db,date(2026,9,1),date(2026,9,30),source=DEMO_SOURCE); b=build_gold(db,date(2030,1,1),date(2030,1,2),source=DEMO_SOURCE)
    assert sum(x["reviews"] for x in a["locations"])>0 and sum(x["reviews"] for x in b["locations"])==0


def test_location_comparison_normalizes_volume(db):
    corpus(db); locations=build_gold(db,source=DEMO_SOURCE)["locations"]
    assert all("reviews_with_text" in x and "top_strength_rate" in x and "top_problem_rate" in x for x in locations)


def test_aspect_copy_is_explicit():
    js=frontend(); assert "positivas · ${x.neutral} mixtas/neutras · ${x.negative} negativas" in js and " + · " not in js


def test_sort_by_mentions_is_available(): assert "Más mencionados" in frontend() and "reviewAspectSort" in frontend()


def test_sort_by_positive_is_available(): assert "Más positivos" in frontend() and "b[k]-a[k]" in frontend()


def test_sort_by_negative_is_available(): assert "Más negativos" in frontend() and "data-v271-topic" in frontend()


def test_evidence_interaction_remains_available(db):
    corpus(db); g=build_gold(db,aspect="temperatura",source=DEMO_SOURCE)
    assert g["topics"][0]["evidence"] and "EVIDENCIAS TRAZABLES" in frontend()


def test_game_master_is_entity_not_topic():
    r=analyze_review("Aster fue fantástico pero hacía mucho calor.",4,["Aster"]); aspects={x["aspect"]:x["sentiment"] for x in r["aspects"]}
    assert aspects["atencion_equipo"]=="positivo" and aspects["temperatura"]=="negativo"
    assert r["entities"]==[{"name":"Aster","type":"known_game_master","confidence":1.0}] and "Aster" not in aspects


def test_fran_remains_person_candidate_not_topic():
    r=analyze_review("Nos atendió Zorik y fue genial.",5)
    assert any(x["name"]=="Zorik" and x["type"]=="person_candidate" for x in r["entities"])
    assert "Zorik" not in {x["aspect"] for x in r["aspects"]}


def test_demo_and_real_remain_explicitly_separated(db):
    corpus(db); demo=build_gold(db,source=DEMO_SOURCE); real=build_gold(db,source=GOOGLE_SOURCE)
    assert demo["source"]["is_demo"] is True and real["source"]["is_demo"] is False and real["kpis"]["reviews"]==0
