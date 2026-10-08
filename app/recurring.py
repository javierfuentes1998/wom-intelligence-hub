import uuid
from datetime import date,timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from .models import Expense,RecurringExpensePlan

def occurrences(plan,start,end):
    cur=max(start,plan.valid_from);limit=min(end,plan.valid_to) if plan.valid_to else end
    while cur<=limit:
        yield cur
        if plan.periodicity=="weekly":cur+=timedelta(days=7)
        elif plan.periodicity=="monthly":cur=(cur.replace(day=28)+timedelta(days=4)).replace(day=min(plan.valid_from.day,28))
        elif plan.periodicity=="quarterly":
            for _ in range(3):cur=(cur.replace(day=28)+timedelta(days=4)).replace(day=min(plan.valid_from.day,28))
        elif plan.periodicity=="annual":
            try:cur=cur.replace(year=cur.year+1)
            except ValueError:cur=cur.replace(year=cur.year+1,day=28)
        elif plan.periodicity.startswith("custom:"):
            _,raw_n,unit=plan.periodicity.split(":");n=int(raw_n)
            if unit=="days":cur+=timedelta(days=n)
            elif unit=="weeks":cur+=timedelta(weeks=n)
            elif unit=="months":
                for _ in range(n):cur=(cur.replace(day=28)+timedelta(days=4)).replace(day=min(plan.valid_from.day,28))
            elif unit=="years":
                try:cur=cur.replace(year=cur.year+n)
                except ValueError:cur=cur.replace(year=cur.year+n,day=28)
        else:raise ValueError("Periodicidad no soportada")

def materialize(db:DB,plan:RecurringExpensePlan,start:date,end:date):
    created=[]
    for d in occurrences(plan,start,end):
        key=f"{plan.id}:{d.isoformat()}"
        if db.scalar(select(Expense).where(Expense.recurrence_key==key)):continue
        x=Expense(id=str(uuid.uuid5(uuid.NAMESPACE_URL,key)),concept=plan.concept,category_id=plan.category_id,amount=plan.amount,expense_date=d,location_id=plan.location_id,room_id=plan.room_id,recurring=True,periodicity=plan.periodicity,recurrence_key=key);db.add(x);created.append(x)
    db.commit();return created
