from calendar import monthrange
from datetime import date, timedelta
import math

def period_bounds(mode: str, anchor: date, custom_start: date|None=None, custom_end: date|None=None):
    if mode=="week": start=anchor-timedelta(days=anchor.weekday()); end=start+timedelta(days=6)
    elif mode=="month": start=anchor.replace(day=1); end=anchor.replace(day=monthrange(anchor.year,anchor.month)[1])
    elif mode=="year": start=date(anchor.year,1,1); end=date(anchor.year,12,31)
    elif mode=="custom" and custom_start and custom_end: start,end=custom_start,custom_end
    else: raise ValueError("Periodo inválido")
    return start,end

def shift_period(mode,start,end,direction):
    if mode=="week": return start+timedelta(weeks=direction),end+timedelta(weeks=direction)
    if mode=="year": return date(start.year+direction,1,1),date(end.year+direction,12,31)
    if mode=="month":
        y=start.year+(start.month-1+direction)//12;m=(start.month-1+direction)%12+1
        return date(y,m,1),date(y,m,monthrange(y,m)[1])
    days=(end-start).days+1; return start+timedelta(days=days*direction),end+timedelta(days=days*direction)

def previous_year(start,end):
    def repl(d):
        try:return d.replace(year=d.year-1)
        except ValueError:return d.replace(year=d.year-1,day=28)
    return repl(start),repl(end)

def granularity(mode): return "day" if mode in ("week","month","custom") else "month"

def initial_anchor(current_start:date,current_end:date,last_data:date|None,explicit=False):
    """Return the last data date only for an automatic initial period fully after available data."""
    if explicit or last_data is None or last_data>=current_start:return None
    return last_data

def nice_ticks(minimum:float,maximum:float,count:int=6):
    if minimum==maximum:
        if maximum==0:return [0.0,1.0]
        minimum=min(0.0,minimum);maximum*=1.1
    rough=(maximum-minimum)/max(1,count-1);magnitude=10**math.floor(math.log10(max(rough,1e-9)))
    choices=[x*magnitude for x in (1,2,2.5,5,10)];step=min(choices,key=lambda x:abs(x-rough))
    while math.ceil(maximum/step)-math.floor(minimum/step)+1>7 and choices.index(step)<len(choices)-1:
        step=choices[choices.index(step)+1]
    low=math.floor(minimum/step)*step;high=math.ceil(maximum/step)*step
    return [round(low+i*step,8) for i in range(round((high-low)/step)+1)]

def x_tick_indices(length:int,mobile=False):
    wanted=4 if mobile else 7
    if length<=wanted:return list(range(length))
    return sorted({round(i*(length-1)/(wanted-1)) for i in range(wanted)})
