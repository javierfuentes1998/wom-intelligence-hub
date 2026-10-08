import time
from datetime import date
from pathlib import Path

import pytest

import app.chat as chat
from app.chat import answer
from app.models import Expense, ExpenseCategory
from app.service import kpis
from tests.test_v240 import seed


CTX = {"start": "2026-09-01", "end": "2026-09-30", "page": "dashboard"}


@pytest.fixture()
def wom_db(db):
    seed(db)
    category = ExpenseCategory(name="operación")
    db.add(category); db.flush()
    db.add(Expense(id="WOM3000-E", concept="Gasto operativo", category_id=category.id,
                   amount=75, expense_date=date(2026, 9, 3), location_id="LA_FLORIDA"))
    db.commit()
    return db


@pytest.mark.parametrize("question,tool", [
    ("¿Cuánto hemos facturado este mes?", "get_revenue"),
    ("¿Cuántos gastos tenemos este mes?", "expenses"),
    ("¿Cuál es el beneficio?", "finance"),
    ("¿Cuál es el margen?", "finance"),
    ("¿Cuántas reservas tenemos?", "reservations"),
    ("¿Cuántos jugadores hemos tenido?", "players"),
    ("¿Cuál es la ocupación?", "occupancy"),
    ("¿Cuál es el ticket medio?", "average_ticket"),
    ("¿Cuántas sesiones tenemos?", "sessions"),
    ("¿Qué sala ha facturado más?", "rooms"),
    ("¿Qué sala tiene más reservas?", "rooms"),
    ("¿Qué local ha generado más ingresos?", "locations"),
    ("¿Cómo están las reseñas?", "reviews"),
    ("¿Qué previsión hay para el próximo mes?", "forecast"),
    ("¿Hay alertas importantes?", "alerts"),
])
def test_minimum_intent_catalog(wom_db, question, tool):
    result = answer(wom_db, question, CTX, use_llm=False)
    assert result["status"] == "ok"
    assert result["tool"] == tool
    assert result["answer"]


def test_room_summary_and_explicit_filter_context(wom_db):
    result = answer(wom_db, "¿Cuántas reservas tiene El Sótano?", CTX, use_llm=False)
    assert result["tool"] == "rooms"
    assert result["data"]["room"]["id"] == "SOTANO"
    assert "El Sótano" in result["answer"] and "1 reservas" in result["answer"]
    context = {**CTX, "room_id": "SOTANO"}
    contextual = answer(wom_db, "¿Cuántas reservas tiene?", context, use_llm=False)
    assert contextual["data"]["value"] == 1
    assert "El Sótano" in contextual["answer"]


def test_language_variants_resolve_same_validated_metric(wom_db):
    values = [answer(wom_db, q, CTX, use_llm=False)["data"]["value"] for q in
              ("facturación", "ingresos", "cuánto hemos facturado", "cuánto hemos ingresado")]
    assert len(set(values)) == 1
    player_values = [answer(wom_db, q, CTX, use_llm=False)["data"]["value"] for q in
                     ("jugadores", "clientes")]
    assert len(set(player_values)) == 1


def test_consistency_with_hub_services(wom_db):
    expected = kpis(wom_db, date(2026, 9, 1), date(2026, 9, 30))["kpis"]
    assert answer(wom_db, "facturación", CTX)["data"]["value"] == expected["revenue"]["value"]
    assert answer(wom_db, "reservas", CTX)["data"]["value"] == expected["reservations"]["value"]
    assert answer(wom_db, "ocupación", CTX)["data"]["value"] == expected["occupancy"]["value"]


def test_hallucination_guards_and_read_only(wom_db):
    assert answer(wom_db, "¿Por qué han bajado los ingresos?", CTX)["status"] == "clarification"
    assert "ingresos, reservas u ocupación" in answer(wom_db, "¿Cuál es la mejor sala?", CTX)["answer"]
    assert answer(wom_db, "¿Cuánto ganaremos en 2035?", CTX)["status"] == "unsupported"
    assert "nómina" in answer(wom_db, "¿Cuánto cobra Aster?", CTX)["answer"]
    assert answer(wom_db, "Añade un gasto de 10 euros", CTX)["status"] == "refused"


def test_basic_intents_do_not_depend_on_llm(wom_db, monkeypatch):
    monkeypatch.setattr(chat.settings, "gemini_api_key", "configured")
    monkeypatch.setattr(chat, "_gemini_with_timeout", lambda _: pytest.fail("A known intent must not call the LLM"))
    for question in ("ingresos", "gastos", "beneficio", "margen", "reservas", "jugadores", "ocupación", "ticket medio"):
        result = answer(wom_db, question, CTX, use_llm=True)
        assert result["status"] == "ok" and result["provider"] == "local"


def test_llm_classifier_timeout_returns_control(monkeypatch):
    monkeypatch.setattr(chat.settings, "llm_timeout_seconds", 0)
    monkeypatch.setattr(chat, "_gemini", lambda _: (time.sleep(1.5), "{}")[1])
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        chat._gemini_with_timeout("test")
    assert time.monotonic() - started < 1.3


def test_frontend_timeout_mascot_and_accessible_contract():
    root = Path(__file__).parents[1]
    js = (root / "frontend" / "app.js").read_text(encoding="utf-8")
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    svg = (root / "frontend" / "wom-3000.svg").read_text(encoding="utf-8")
    assert "AbortController" in js and "12000" in js and "finally" in js
    assert "WOM 3000 está consultando los datos" in js
    assert "shiftKey" in js and "sessionStorage" in js
    assert "data-chat-suggestion" in html and "Asistente del Intelligence Hub" in html
    assert "WOM 3000" in html and "wom-3000.svg" in html
    assert svg.count("#ef3645") >= 1 and "WOM 3000" in svg
