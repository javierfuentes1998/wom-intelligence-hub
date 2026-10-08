import re

ASPECTS = {
 "game_master": ["game master", "monitor", "gm"], "dificultad": ["difícil", "facil", "fácil", "dificultad"],
 "actores": ["actor", "actriz"], "ambientacion": ["ambientación", "decoración", "inmersión"],
 "precio": ["precio", "caro", "barato"], "puzzles": ["puzzle", "prueba", "acertijo"],
 "instalaciones": ["instalación", "baño", "local"], "temperatura": ["calor", "frío", "temperatura"],
 "espera": ["espera", "tardaron", "retraso", "minutos"], "atencion": ["atención", "trato"],
 "mantenimiento": ["roto", "avería", "mantenimiento"], "miedo":["miedo","terror","susto"],
 "duracion":["duración","corto","largo"], "inmersion":["inmersión","inmersivo"], "originalidad":["original","originalidad"]}
POS = {"genial","increíble","excelente","divertido","bueno","encantó","recomendable","amable"}
NEG = {"mal","malo","caro","roto","calor","frío","espera","retraso","decepcionante"}

def normalize(text: str) -> str: return re.sub(r"\s+", " ", text.lower().strip())
def classify(text: str):
    clean = normalize(text); words = set(re.findall(r"\w+", clean)); score = len(words & POS)-len(words & NEG)
    label = "positivo" if score > 0 else "negativo" if score < 0 else "neutral"
    strength = min(abs(score)/3, 1.0)
    aspects = []
    clauses=[c.strip() for c in re.split(r"\bpero\b|[.;]",clean) if c.strip()]
    for name, terms in ASPECTS.items():
        matching=[c for c in clauses if any(t in c for t in terms)]
        if matching:
            local=" ".join(matching);local_score=sum(1 for w in POS if w in local)-sum(1 for w in NEG if w in local)
            aspects.append({"aspect": name, "sentiment": "positivo" if local_score>0 else "negativo" if local_score<0 else "neutral"})
    return {"processed_text": clean, "sentiment": label, "score": strength, "aspects": aspects or [{"aspect":"otros","sentiment":label}]}
