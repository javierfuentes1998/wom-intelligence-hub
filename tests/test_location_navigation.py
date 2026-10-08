from pathlib import Path
from app.models import Location


APP_JS = (Path(__file__).parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")
LOCATION_IDS = ("LA_FLORIDA", "ALTOZANO", "LOS_ANGELES", "ORIHUELA")


def test_demo_locations_expose_the_internal_ids_used_by_navigation(client, db):
    db.add_all(Location(id=location_id, name=location_id) for location_id in LOCATION_IDS)
    db.commit()
    locations = {item["id"]: item for item in client.get("/api/locations").json()}
    assert set(LOCATION_IDS) <= locations.keys()


def test_location_cards_keep_internal_ids_and_human_names_are_presentation_only():
    for location_id in LOCATION_IDS:
        assert f"{location_id}:" in APP_JS
    assert 'data-location="${x.id}"' in APP_JS
    assert "all.some(x=>x.id===selected)" in APP_JS


def test_valid_location_navigation_stays_in_locations_without_dashboard_fallback():
    handler = APP_JS.split("function bindDynamic(){", 1)[1].split("function chatChart", 1)[0]
    location_handler = handler.split("document.querySelectorAll('[data-location]')", 1)[1].split("document.querySelectorAll('[data-room]')", 1)[0]
    assert "S.page='locations'" in location_handler
    assert "S.page='dashboard'" not in location_handler
    assert "some(x=>x.value===id)" in location_handler


def test_persistent_location_selector_replaces_back_navigation_without_changing_period():
    assert 'class="location-selector"' in APP_JS
    assert "data-location-back" not in APP_JS
    handler = APP_JS.split("document.querySelectorAll('[data-location]')", 1)[1].split("document.querySelectorAll('[data-room]')", 1)[0]
    assert "S.page='locations'" in handler
    assert "setPeriod" not in handler
    assert "S.anchor" not in handler
