from datetime import date, datetime, timedelta
from math import sqrt
from statistics import mean

def safe_margin(revenue: float, profit: float): return round(profit/revenue*100, 2) if revenue else None
def comparison(current: float, previous: float):
    return {"absolute": round(current-previous,2), "percent": round((current-previous)/previous*100,2) if previous else None}
def seasonal_naive(values: list[float], horizon=4, season=4):
    if len(values) < season: return None
    return [round(values[-season+i%season],2) for i in range(horizon)]
def backtest_seasonal(values: list[float], season=4):
    if len(values) < season*2: return None
    actual=values[-season:]; pred=values[-season*2:-season]
    errors=[a-p for a,p in zip(actual,pred)]
    return {"mae":round(mean(abs(e) for e in errors),2),"rmse":round(sqrt(mean(e*e for e in errors)),2),"wape":round(sum(abs(e) for e in errors)/sum(abs(a) for a in actual)*100,2) if sum(abs(a) for a in actual) else None}
def robust_anomalies(points: list[dict], threshold=3.5):
    if len(points)<8:return []
    vals=sorted(float(p["value"]) for p in points); med=vals[len(vals)//2]; deviations=sorted(abs(v-med) for v in vals); mad=deviations[len(deviations)//2] or 1
    out=[]
    for p in points:
        z=.6745*(float(p["value"])-med)/mad
        if abs(z)>threshold: out.append({**p,"magnitude":round(z,2),"explanation":"Desviación robusta frente a la mediana histórica comparable."})
    return out
def room_health(revenue_trend, occupancy, rating, sentiment, cancellations):
    components={"tendencia_ingresos":max(0,min(100,50+revenue_trend*2)),"ocupacion":occupancy,"valoracion":rating/5*100,"sentimiento":sentiment,"cancelaciones":100-cancellations}
    weights={"tendencia_ingresos":.25,"ocupacion":.25,"valoracion":.2,"sentimiento":.2,"cancelaciones":.1}
    return {"score":round(sum(components[k]*weights[k] for k in weights),1),"components":{k:round(v,1) for k,v in components.items()},"weights":weights,"experimental":True}
