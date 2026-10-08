from datetime import date
from app.models import ExpenseCategory,Location,RecurringExpensePlan
from app.recurring import materialize,occurrences
def setup(db,amount=100,valid_from=date(2026,1,1),valid_to=None):
    db.add(Location(id="L",name="Local"));db.add(ExpenseCategory(id=1,name="alquiler"));db.flush();p=RecurringExpensePlan(id="P",concept="Alquiler",category_id=1,amount=amount,location_id="L",periodicity="monthly",valid_from=valid_from,valid_to=valid_to);db.add(p);db.commit();return p
def test_monthly_materialization_is_idempotent(db):
    p=setup(db);assert len(materialize(db,p,date(2026,1,1),date(2026,3,31)))==3;assert len(materialize(db,p,date(2026,1,1),date(2026,3,31)))==0
def test_plan_end_date(db):
    p=setup(db,valid_to=date(2026,2,28));assert len(materialize(db,p,date(2026,1,1),date(2026,4,30)))==2
def test_future_price_change_preserves_history(db):
    p=setup(db,100,valid_to=date(2026,5,31));materialize(db,p,date(2026,1,1),date(2026,5,31));p2=RecurringExpensePlan(id="P2",concept="Alquiler",category_id=1,amount=120,location_id="L",periodicity="monthly",valid_from=date(2026,6,1));db.add(p2);db.commit();materialize(db,p2,date(2026,6,1),date(2026,7,31));from app.models import Expense;rows=db.query(Expense).order_by(Expense.expense_date).all();assert [x.amount for x in rows]==[100]*5+[120]*2
def test_weekly_occurrences(db):
    p=setup(db);p.periodicity="weekly";assert len(list(occurrences(p,date(2026,1,1),date(2026,1,15))))==3
def test_custom_recurrence_is_bounded_and_supports_units(db):
    p=setup(db);p.periodicity="custom:2:weeks";assert list(occurrences(p,date(2026,1,1),date(2026,2,1)))==[date(2026,1,1),date(2026,1,15),date(2026,1,29)]
    p.periodicity="custom:3:months";assert list(occurrences(p,date(2026,1,1),date(2026,12,31)))==[date(2026,1,1),date(2026,4,1),date(2026,7,1),date(2026,10,1)]
