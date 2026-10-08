import sqlite3
from pathlib import Path

def test_demo_september_first_peak_is_monthly_recurring():
    path=Path(__file__).parents[1]/"data"/"wom_hub.db"
    connection=sqlite3.connect(path)
    rows=connection.execute("select amount,recurring,periodicity from fact_expense where expense_date='2026-09-01' and voided=0").fetchall()
    assert len(rows)==16
    assert sum(row[0] for row in rows)==32000
    assert all(row[1] and row[2]=='monthly' for row in rows)
