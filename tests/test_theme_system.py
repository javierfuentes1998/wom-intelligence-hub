import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THEME_JS = ROOT / "frontend" / "theme.js"


def run_node(expression: str):
    script = f"const t=require({json.dumps(str(THEME_JS))}); console.log(JSON.stringify({expression}));"
    completed = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    )
    return json.loads(completed.stdout)


def test_auto_theme_exact_boundaries():
    cases = run_node("[\
      t.themeForLocalTime(new Date(2026,9,7,7,59,59)),\
      t.themeForLocalTime(new Date(2026,9,7,8,0,0)),\
      t.themeForLocalTime(new Date(2026,9,7,8,1,0)),\
      t.themeForLocalTime(new Date(2026,9,7,20,29,59)),\
      t.themeForLocalTime(new Date(2026,9,7,20,30,0)),\
      t.themeForLocalTime(new Date(2026,9,7,20,31,0)),\
      t.themeForLocalTime(new Date(2026,9,7,23,59,0)),\
      t.themeForLocalTime(new Date(2026,9,8,0,0,0))]")
    assert cases == ["dark", "light", "light", "light", "dark", "dark", "dark", "dark"]


def test_manual_preferences_override_time_and_invalid_values_use_auto():
    result = run_node("[\
      t.effectiveTheme('auto',new Date(2026,9,7,15,0)),\
      t.effectiveTheme('auto',new Date(2026,9,7,23,0)),\
      t.effectiveTheme('light',new Date(2026,9,7,23,0)),\
      t.effectiveTheme('dark',new Date(2026,9,7,12,0)),\
      t.effectiveTheme('invalid',new Date(2026,9,7,12,0)),\
      t.normalizePreference(null)]")
    assert result == ["light", "dark", "light", "dark", "light", "auto"]


def test_next_transition_is_scheduled_at_exact_local_boundary():
    result = run_node("[\
      t.nextBoundary(new Date(2026,9,7,7,59,59)).toISOString(),\
      t.millisecondsUntilNextBoundary(new Date(2026,9,7,7,59,59)),\
      t.nextBoundary(new Date(2026,9,7,20,29,59)).toISOString(),\
      t.millisecondsUntilNextBoundary(new Date(2026,9,7,20,29,59))]")
    assert result[1] == 1000
    assert result[3] == 1000
    assert result[0].endswith("08:00:00.000Z") or result[0].endswith("06:00:00.000Z")
    assert result[2].endswith("20:30:00.000Z") or result[2].endswith("18:30:00.000Z")


def test_controller_persists_and_auto_transitions_without_polling():
    result = run_node("(()=>{\
      let value=null,now=new Date(2026,9,7,20,29,59),scheduled=[],applied=[];\
      const storage={getItem:()=>value,setItem:(_,v)=>value=v};\
      const c=t.createController({storage,now:()=>now,schedule:(fn,ms)=>{scheduled.push({fn,ms});return scheduled.length},cancel:()=>{},apply:s=>applied.push(s.theme)});\
      c.refresh(); const delay=scheduled[0].ms; now=new Date(2026,9,7,20,30,0); scheduled[0].fn();\
      c.setPreference('light'); return {value,delay,applied,timers:scheduled.length};\
    })()")
    assert result == {
        "value": "light",
        "delay": 1025,
        "applied": ["light", "dark", "light"],
        "timers": 2,
    }


def test_controller_transitions_from_night_to_day_at_eight():
    result = run_node("(()=>{\
      let now=new Date(2026,9,7,7,59,59),scheduled=[],applied=[];\
      const storage={getItem:()=>\"auto\",setItem:()=>{}};\
      const c=t.createController({storage,now:()=>now,schedule:(fn,ms)=>{scheduled.push({fn,ms});return scheduled.length},cancel:()=>{},apply:s=>applied.push(s.theme)});\
      c.refresh(); now=new Date(2026,9,7,8,0,0); scheduled[0].fn();\
      return {delay:scheduled[0].ms,applied,timers:scheduled.length};\
    })()")
    assert result == {"delay": 1025, "applied": ["dark", "light"], "timers": 2}


def test_index_loads_theme_before_css_and_exposes_three_state_control():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert html.index("theme.js") < html.index("styles.css")
    assert 'data-theme-choice="auto"' in html
    assert 'data-theme-choice="light"' in html
    assert 'data-theme-choice="dark"' in html
    assert "theme.css" in html


def test_light_theme_preserves_demand_semantic_colours():
    theme = (ROOT / "frontend" / "theme.css").read_text(encoding="utf-8")
    demand = (ROOT / "frontend" / "v22-extra.css").read_text(encoding="utf-8")
    for token in ("none", "low", "medium", "high", "max", "unavailable"):
        assert f"--demand-{token}:" in theme
        assert f"var(--demand-{token})" in demand
    assert ':root[data-theme="light"] .demand-map-cell {' not in theme
    assert ".demand-map-cell:hover" in demand
    assert ".demand-map-cell:focus" in demand
