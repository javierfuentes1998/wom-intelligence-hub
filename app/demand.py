from statistics import median

STATES=[("muy_mal","red"),("regular","yellow"),("bien","green"),("sobresaliente","blue")]
def contextual_state(current:float, comparable:list[float], minimum=8):
    if len(comparable)<minimum:return {"state":"insufficient_data","color":"gray","ratio":None}
    base=median(comparable)
    if base==0:return {"state":"insufficient_data","color":"gray","ratio":None}
    ratio=current/base
    # Umbrales relativos a la mediana de la misma sala/día/hora/temporada.
    idx=0 if ratio<.6 else 1 if ratio<.9 else 2 if ratio<1.25 else 3
    return {"state":STATES[idx][0],"color":STATES[idx][1],"ratio":round(ratio,2)}
