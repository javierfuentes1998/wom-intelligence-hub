from app.chat import answer,chart_spec
from app.models import Alert
def test_write_attempt_refused(db): assert answer(db,"DROP TABLE sesiones")["status"]=="refused"
def test_valid_chart(): assert chart_spec("bar",["a"],[{"label":"x","values":[1]}])["type"]=="bar"
def test_invalid_chart_rejected():
    import pytest
    with pytest.raises(ValueError):chart_spec("script",[],[])
def test_unknown_question_graceful(db): assert answer(db,"qué tal")["status"]=="unsupported"
def test_alert_seen(client,db):
    db.add(Alert(id="A",category="Datos",severity="atención",title="T",explanation="E",evidence="{}"));db.commit();assert client.get('/api/alerts').json()[0]["seen"] is False;assert client.patch('/api/alerts/A/seen').json()["seen"] is True
def test_alert_not_found(client): assert client.patch('/api/alerts/no/seen').status_code==404
