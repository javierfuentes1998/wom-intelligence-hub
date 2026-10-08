from datetime import date
import pytest
from app.temporal import granularity,initial_anchor,nice_ticks,period_bounds,previous_year,shift_period,x_tick_indices

def test_week_is_monday_to_sunday(): assert period_bounds("week",date(2026,9,29))==(date(2026,9,28),date(2026,10,4))
def test_week_one_crosses_year(): assert period_bounds("week",date(2027,1,1))==(date(2026,12,28),date(2027,1,3))
def test_month_leap_year(): assert period_bounds("month",date(2024,2,10))==(date(2024,2,1),date(2024,2,29))
def test_year_bounds_and_granularity(): assert period_bounds("year",date(2026,5,2))==(date(2026,1,1),date(2026,12,31)) and granularity("year")=="month"
def test_custom_period(): assert period_bounds("custom",date.today(),date(2026,1,2),date(2026,1,9))==(date(2026,1,2),date(2026,1,9))
def test_invalid_period():
    with pytest.raises(ValueError):period_bounds("bad",date.today())
def test_shift_month_over_year(): assert shift_period("month",date(2026,1,1),date(2026,1,31),-1)==(date(2025,12,1),date(2025,12,31))
def test_previous_year_leap_day(): assert previous_year(date(2024,2,29),date(2024,3,2))[0]==date(2023,2,28)

def test_initial_period_fallback_rules():
    start,end=date(2026,10,1),date(2026,10,31)
    assert initial_anchor(start,end,date(2026,9,29))==date(2026,9,29)
    assert initial_anchor(start,end,date(2026,10,3)) is None
    assert initial_anchor(start,end,date(2026,9,29),explicit=True) is None
    assert initial_anchor(start,end,None) is None

def test_nice_tick_ranges():
    for low,high in ((0,83),(0,147),(0,1730),(-500,1500),(0,100)):
        ticks=nice_ticks(low,high)
        assert ticks==sorted(set(ticks)) and 2<=len(ticks)<=7
        assert ticks[0]<=low and ticks[-1]>=high

def test_adaptive_x_tick_density():
    assert x_tick_indices(7)==list(range(7))
    assert len(x_tick_indices(30))==7
    assert len(x_tick_indices(365))==7
    assert len(x_tick_indices(730,mobile=True))==4
