from app.analytics import backtest_seasonal, comparison, robust_anomalies, room_health, safe_margin, seasonal_naive

def test_profit_margin_and_zero():
    assert safe_margin(100,25)==25
    assert safe_margin(0,0) is None
def test_comparison_without_division_by_zero(): assert comparison(10,0)["percent"] is None
def test_forecast_requires_history(): assert seasonal_naive([1,2],season=4) is None
def test_seasonal_forecast_and_backtest():
    assert seasonal_naive([1,2,3,4,2,3,4,5],2,4)==[2,3]
    assert backtest_seasonal([1,2,3,4,2,3,4,5],4)["mae"]==1
def test_robust_anomaly_empty_and_detected():
    assert robust_anomalies([])==[]
    points=[{"value":10,"date":str(i)} for i in range(9)]+[{"value":100,"date":"x"}]
    assert robust_anomalies(points)[0]["date"]=="x"
def test_health_is_interpretable():
    x=room_health(2,70,4,80,5); assert 0<=x["score"]<=100 and sum(x["weights"].values())==1
