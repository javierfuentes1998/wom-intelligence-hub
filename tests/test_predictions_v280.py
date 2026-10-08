from datetime import date,datetime,timedelta

import pytest

from app.models import Location,Room,Session
from app.predictions import (_resample,business_prediction)


def dims(db):
    db.add_all([Location(id="L1",name="Local 1"),Location(id="L2",name="Local 2"),Room(id="R1",location_id="L1",name="Sala 1",capacity=8),Room(id="R2",location_id="L2",name="Sala 2",capacity=8)]);db.commit()


def add(db,prefix,room,start,count,revenue=100,spread=7):
    for i in range(count):
        day=start+timedelta(days=i%spread)
        db.add(Session(id=f"{prefix}-{i}",room_id=room,starts_at=datetime.combine(day,datetime.min.time())+timedelta(hours=12),status="completed",customers=4,revenue=revenue,available=True))
    db.commit()


def weekly(db,annual=10,recent=20):
    dims(db);add(db,"history","R1",date(2024,1,1),1)
    add(db,"annual","R1",date(2025,10,6),annual,100)
    add(db,"recent","R1",date(2026,9,21),recent,200)
    add(db,"partial","R1",date(2026,9,29),1,50)
    return business_prediction(db,"week")


def monthly(db,annual=10,recent=20):
    dims(db);add(db,"history","R1",date(2024,1,1),1)
    add(db,"annual","R1",date(2025,10,1),annual,100,31)
    add(db,"recent","R1",date(2026,8,1),recent,200,31)
    add(db,"partial","R1",date(2026,9,29),1,50)
    return business_prediction(db,"month")


def js():return open("frontend/predictions-v280.js",encoding="utf-8").read()


def test_weekly_5050_reservations(db):
    x=weekly(db,10,20);assert x["prediction"]["reservations"]["exact"]==15


def test_weekly_5050_revenue(db):
    x=weekly(db,10,20);assert x["prediction"]["revenue"]["exact"]==2500


def test_week_is_monday_to_sunday(db):
    x=weekly(db);start=date.fromisoformat(x["target"]["start"]);end=date.fromisoformat(x["target"]["end"])
    assert start.weekday()==0 and end.weekday()==6 and (end-start).days==6


def test_weekly_days_align_by_weekday(db):
    x=weekly(db);assert [p["label"] for p in x["daily"]]==["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    assert date.fromisoformat(x["references"]["annual"]["start"]).weekday()==0


def test_weekly_daily_sum_equals_total(db):
    x=weekly(db);assert sum(p["prediction"]["reservations"] for p in x["daily"])==pytest.approx(x["prediction"]["reservations"]["exact"])
    assert sum(p["prediction"]["revenue"] for p in x["daily"])==pytest.approx(x["prediction"]["revenue"]["exact"])


def test_week_alignment_survives_year_change(db):
    dims(db);add(db,"old","R1",date(2024,12,30),7);add(db,"recent","R1",date(2025,12,22),7);add(db,"last","R1",date(2025,12,30),1)
    x=business_prediction(db,"week");assert date.fromisoformat(x["target"]["start"]).weekday()==0 and date.fromisoformat(x["references"]["annual"]["start"]).weekday()==0


def test_company_scope_includes_all_rooms(db):
    dims(db);add(db,"history","R1",date(2024,1,1),1);add(db,"a1","R1",date(2025,10,6),4);add(db,"a2","R2",date(2025,10,6),6);add(db,"r1","R1",date(2026,9,21),4);add(db,"r2","R2",date(2026,9,21),6);add(db,"p","R1",date(2026,9,29),1)
    assert business_prediction(db,"week")["prediction"]["reservations"]["exact"]==10


def test_location_scope_does_not_mix_locations(db):
    dims(db);add(db,"history","R1",date(2024,1,1),1);add(db,"a1","R1",date(2025,10,6),4);add(db,"a2","R2",date(2025,10,6),40);add(db,"r1","R1",date(2026,9,21),6);add(db,"r2","R2",date(2026,9,21),60);add(db,"p","R1",date(2026,9,29),1)
    assert business_prediction(db,"week",location_id="L1")["prediction"]["reservations"]["exact"]==5


def test_room_scope_does_not_mix_rooms(db):
    dims(db);add(db,"history","R1",date(2024,1,1),1);add(db,"a1","R1",date(2025,10,6),8);add(db,"a2","R2",date(2025,10,6),40);add(db,"r1","R1",date(2026,9,21),12);add(db,"r2","R2",date(2026,9,21),60);add(db,"p","R1",date(2026,9,29),1)
    assert business_prediction(db,"week",room_id="R1")["prediction"]["reservations"]["exact"]==10


def test_incompatible_room_location_is_rejected(db):
    dims(db)
    with pytest.raises(ValueError):business_prediction(db,"week",location_id="L1",room_id="R2")


def test_no_history_is_explicit(db):
    dims(db);assert business_prediction(db,"week")["status"]=="insufficient_data"


def test_partial_history_is_provisional(db):
    dims(db);add(db,"recent","R1",date(2026,9,7),5);add(db,"partial","R1",date(2026,9,16),1)
    x=business_prediction(db,"week",room_id="R1");assert x["status"]=="provisional_recent_only" and x["prediction"]["reservations"]["applied_weights"]==(0,1)


def test_reservation_rounding_is_discrete(db):
    x=weekly(db,11,20);assert x["prediction"]["reservations"]["exact"]==15.5 and x["prediction"]["reservations"]["display"]==16


def test_monthly_7030_reservations(db):assert monthly(db,10,20)["prediction"]["reservations"]["exact"]==13


def test_monthly_7030_revenue(db):assert monthly(db,10,20)["prediction"]["revenue"]["exact"]==1900


def test_financial_rounding_uses_half_up(db):
    dims(db);add(db,"history","R1",date(2024,1,1),1);add(db,"annual","R1",date(2025,10,1),1,1);add(db,"recent","R1",date(2026,8,1),1,6);add(db,"partial","R1",date(2026,9,29),1,1)
    result=business_prediction(db,"month");assert result["prediction"]["revenue"]["exact"]==2.5 and result["prediction"]["revenue"]["display"]==3


def test_month_references_previous_and_prior_year(db):
    x=monthly(db);assert x["target"]["start"]=="2026-10-01" and x["references"]["annual"]["start"]=="2025-10-01" and x["references"]["recent"]["start"]=="2026-08-01"


def test_next_complete_period_after_2026_09_29(db):
    x=monthly(db);assert x["target"]["start"]=="2026-10-01" and x["target"]["end"]=="2026-10-31"
    y=business_prediction(db,"week");assert y["target"]["start"]=="2026-10-05" and y["target"]["end"]=="2026-10-11"


@pytest.mark.parametrize("cutoff,expected",[(date(2026,9,16),date(2026,9,21)),(date(2026,9,20),date(2026,9,21)),(date(2026,9,30),date(2026,10,5))])
def test_next_week_is_strictly_after_cutoff(db,cutoff,expected):
    dims(db);add(db,"hist","R1",date(2025,9,1),2);add(db,"recent","R1",expected-timedelta(days=7),2);add(db,"last","R1",cutoff,1)
    assert date.fromisoformat(business_prediction(db,"week")["target"]["start"])==expected


def test_month_reservation_display_reconciles(db):
    x=monthly(db,10,20);shown=[p["prediction_display_reservations"] for p in x["chart"]]
    assert all(isinstance(v,int) for v in shown) and sum(shown)==x["prediction"]["reservations"]["display"]


@pytest.mark.parametrize("last_complete,target_days",[(date(2025,1,31),28),(date(2024,1,31),29),(date(2026,3,31),30),(date(2026,4,30),31)])
def test_month_target_supports_all_lengths(db,last_complete,target_days):
    dims(db);target_start=(last_complete+timedelta(days=1)).replace(day=1);annual=target_start.replace(year=target_start.year-1);recent=last_complete.replace(day=1)
    add(db,"hist","R1",annual,1);add(db,"recent","R1",recent,1);add(db,"last","R1",last_complete,1)
    assert len(business_prediction(db,"month")["daily"])==target_days


def test_month_december_to_january(db):
    dims(db);add(db,"hist","R1",date(2024,1,1),2);add(db,"recent","R1",date(2024,12,1),2);add(db,"last","R1",date(2024,12,31),1)
    x=business_prediction(db,"month");assert x["target"]["start"]=="2025-01-01" and x["references"]["recent"]["start"]=="2024-12-01"


def test_resample_preserves_total():assert sum(_resample([1,2,3,4],31))==pytest.approx(10)


def test_month_distribution_sum_equals_total(db):
    x=monthly(db,13,27)
    for metric in ("reservations","revenue"):assert sum(p["prediction"][metric] for p in x["daily"])==pytest.approx(x["prediction"][metric]["exact"],abs=.05)


def test_month_chart_uses_weeks(db):
    result=monthly(db);assert len(result["chart"])==5 and result["chart"][0]["label"]=="Semana 1"


def test_variation_up_down_and_stable(db):
    up=weekly(db,10,20);assert up["variations"]["annual"]["reservations"]>0 and up["variations"]["recent"]["reservations"]<0


def test_strong_days_only_when_supported(db):
    x=weekly(db,14,14);assert isinstance(x["strong_days"],list)


def test_ui_uses_cautious_noncausal_language():
    text=js();assert "se esperan aproximadamente" in text and "No se atribuyen causas" in text and "garantizado" not in text


def test_ui_hides_technical_model_names():
    text=js();assert all(x not in text for x in ("seasonal_naive","recent_median","year_plus_trend","WAPE","MAE"))


def test_ui_exposes_formula_dates_and_modes():
    text=js();assert "De dónde sale la predicción" in text and "Próxima semana" in text and "Próximo mes" in text and "predDate" in text


def test_api_supports_modes_and_scope(client,db):
    weekly(db);response=client.get("/api/predictions?mode=week&location_id=L1&room_id=R1")
    assert response.status_code==200 and response.json()["mode"]=="week"


def test_api_rejects_bad_mode(client):assert client.get("/api/predictions?mode=quarter").status_code==422
