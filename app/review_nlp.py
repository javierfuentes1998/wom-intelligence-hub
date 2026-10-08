"""Auditable multilingual review analysis for WOM.

The local analyzer is deliberately deterministic: it preserves literal evidence,
normalizes semantically equivalent expressions into a business taxonomy and never
turns people into topics. An optional LLM can be added later behind the same schema.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime

ANALYZER_VERSION = "1.1.0"

ASPECT_PATTERNS = {
    "ambientacion": [r"ambient", r"decoraci", r"setting", r"atmospher"],
    "inmersion": [r"inmersi", r"immers", r"metid[oa] en la historia"],
    "puzzles": [r"puzzle", r"puzle", r"acertijo", r"prueba", r"riddle", r"enigme"],
    "dificultad": [r"dif[ií]cil", r"f[aá]cil", r"dificult", r"too easy", r"too hard"],
    "originalidad": [r"original", r"innovador", r"different", r"unique"],
    "historia": [r"historia", r"narrativ", r"story", r"plot"],
    "actores": [r"actor", r"actriz", r"performer"],
    "terror": [r"miedo", r"terror", r"susto", r"scary", r"fear"],
    "atencion_equipo": [r"game master", r"monitor", r"trato", r"atenci[oó]n", r"staff", r"team", r"nos ayud", r"helped us", r"maj[ií]sim", r"borde"],
    "pistas": [r"pista", r"ayuda", r"hint"],
    "ritmo": [r"ritmo", r"pace"],
    "mantenimiento": [r"roto", r"aver[ií]a", r"mantenimiento", r"broken", r"didn.?t work"],
    "tecnologia": [r"tecnolog", r"mecanismo", r"mechanism"],
    "audio": [r"audio", r"sonido", r"sound"],
    "iluminacion": [r"luz", r"luces", r"ilumin", r"lighting"],
    "temperatura": [r"calor", r"caliente", r"nos asamos", r"aire acondicionado", r"temperatura", r"fr[ií]o", r"too hot", r"air conditioning", r"heat"],
    "limpieza": [r"limpi", r"sucio", r"clean", r"dirty"],
    "instalaciones": [r"instalaci", r"ba[ñn]o", r"facilit"],
    "accesibilidad": [r"accesib", r"wheelchair", r"movilidad"],
    "precio": [r"precio", r"caro", r"barato", r"calidad.precio", r"price", r"expensive", r"value for money"],
    "reserva": [r"reserva", r"compra", r"booking", r"website", r"web"],
    "espera": [r"espera", r"retras", r"puntual", r"tardaron", r"waiting", r"late", r"delay"],
    "duracion": [r"duraci", r"corto", r"largo", r"duration", r"short", r"long"],
    # A bare "grupo/personas/players" is deliberately insufficient: this
    # aspect represents an evaluated shared/group experience, not a noun hit.
    "experiencia_grupo": [
        r"(?:genial|ideal|perfect[oa]?|adecuad[oa]?|recomend\w*).{0,24}(?:grupo|amigos|familia)",
        r"(?:grupo|amigos|familia).{0,24}(?:disfrut|divertid|genial|ideal|perfect|recomend)",
        r"(?:din[aá]mica|tama[ñn]o|n[uú]mero).{0,18}(?:grupo|personas|jugadores)",
        r"(?:experiencia|jugar|jugando).{0,24}(?:en grupo|con amigos|con familia)",
        r"group size", r"great for groups", r"played as a group",
    ],
    "ubicacion": [r"ubicaci", r"acceso", r"aparc", r"location", r"parking"],
    "experiencia_general": [r"experiencia", r"experience", r"escape room"],
}

POSITIVE = [r"incre[ií]ble", r"genial", r"excelente", r"espectacular", r"encant", r"divertid", r"amable", r"maj[ií]sim", r"recomend", r"original", r"fant[aá]st", r"amazing", r"great", r"excellent", r"loved", r"friendly", r"super", r"gut", r"g[eé]nial"]
NEGATIVE = [r"mal[oa]?", r"decepcion", r"borde", r"roto", r"aver[ií]a", r"caro", r"espera", r"retras", r"(?:mucho|demasiado) calor", r"nos asamos", r"faltaba aire", r"no daba nada de miedo", r"demasiado f[aá]cil", r"s[ií],?\s+claro", r"terrible", r"awful", r"bad", r"broken", r"too hot", r"too easy", r"expensive", r"delay"]
NEGATORS = r"(?:no|nunca|nada|sin|not|never|kein|pas)"
LANGUAGE_MARKERS = {
    "es": {"el", "la", "nos", "pero", "muy", "fue", "estaba", "reseña"},
    "en": {"the", "was", "but", "very", "we", "room", "great"},
    "fr": {"le", "la", "mais", "très", "nous", "était"},
    "de": {"der", "die", "aber", "sehr", "war", "wir"},
    "it": {"il", "la", "ma", "molto", "era", "noi"},
}
ROOM_PATTERNS = {
    "SOTANO": [r"el s[oó]tano", r"sotano"], "HAMMER": [r"hammer killer"],
    "RELIQUIAS": [r"reliquias de judy", r"reliquias"], "YUCATAN": [r"yucat[aá]n"],
    "MAGIA": [r"escuela de magia"], "BASILISCO": [r"veneno del basilisco", r"basilisco"],
    "SEMILLAS": [r"semillas de la locura", r"semillas"], "PESADILLAS_II": [r"pesadillas ii", r"pesadillas 2"],
}
ENTITY_EXCLUSIONS = {"Nos", "El", "La", "Las", "Los", "Una", "Un", "WOM", "Google", "Hammer", "Killer", "Yucatán", "Orihuela", "Altozano",
                     "Semillas", "Locura", "Pesadillas", "Veneno", "Basilisco", "Escuela", "Magia", "Reliquias", "Judy", "Sótano"}


def normalize_review(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "").strip())


def content_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def detect_language(text: str) -> str:
    words = set(re.findall(r"[a-záéíóúüñàèìòùäöüß]+", text.casefold()))
    scores = {language: len(words & markers) for language, markers in LANGUAGE_MARKERS.items()}
    language, score = max(scores.items(), key=lambda item: item[1])
    return language if score else "und"


def _clause_score(clause: str) -> tuple[float, list[str]]:
    hits = []
    value = 0.0
    for pattern in POSITIVE:
        if re.search(pattern, clause, re.I):
            negated = re.search(rf"{NEGATORS}.{{0,18}}(?:{pattern})", clause, re.I)
            value += -1 if negated else 1
            hits.append(("negated_positive:" if negated else "positive:") + pattern)
    for pattern in NEGATIVE:
        if re.search(pattern, clause, re.I):
            value -= 1
            hits.append("negative:" + pattern)
    return max(-1.0, min(1.0, value / max(1, len(hits)))), hits


def _sentiment_label(score: float) -> str:
    if score >= 0.6: return "muy_positivo"
    if score >= 0.15: return "positivo"
    if score <= -0.6: return "muy_negativo"
    if score <= -0.15: return "negativo"
    return "mixto_neutral"


def _aspect_sentiment(score: float) -> str:
    return "positivo" if score > 0.1 else "negativo" if score < -0.1 else "neutral"


def _entities(text: str, known_people: set[str]) -> list[dict]:
    found = {}
    folded = text.casefold()
    for person in sorted(known_people,key=len,reverse=True):
        if re.search(rf"\b{re.escape(person.casefold())}\b", folded):
            if any(person.casefold() in item["name"].casefold() for item in found.values()):continue
            found[person.casefold()] = {"name": person, "type": "known_game_master", "confidence": 1.0}
    for candidate in re.findall(r"(?<![.!?]\s)(?<!^)\b[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]{2,}\b", text):
        if candidate not in ENTITY_EXCLUSIONS and candidate.casefold() not in found and not any(candidate.casefold() in item["name"].casefold() for item in found.values()):
            found[candidate.casefold()] = {"name": candidate, "type": "person_candidate", "confidence": 0.68}
    return list(found.values())


def analyze_review(text: str | None, stars: int | None, known_people=(), analyzer_version=ANALYZER_VERSION) -> dict:
    original = text or ""
    clean = normalize_review(original)
    if not clean:
        return {"language": "und", "normalized_text": "", "sentiment_label": None, "sentiment_score": None,
                "confidence": None, "aspects": [], "entities": [], "room_id": None, "room_method": None,
                "room_confidence": None, "star_text_discrepancy": False, "analysis_status": "analyzed",
                "analyzer_method": "hybrid_semantic_rules", "analyzer_version": analyzer_version,
                "analyzed_at": datetime.utcnow().isoformat()}
    clauses = [item.strip() for item in re.split(r"\b(?:pero|aunque|sin embargo|but|however|mais|aber|ma)\b|[.;!?]", clean, flags=re.I) if item.strip()]
    people = _entities(original, set(known_people))
    aspects = []
    for clause in clauses:
        score, hits = _clause_score(clause.casefold())
        matched = [name for name, patterns in ASPECT_PATTERNS.items() if any(re.search(pattern, clause, re.I) for pattern in patterns)]
        if people and any(entity["name"].casefold() in clause.casefold() for entity in people):
            matched.append("atencion_equipo")
        for name in dict.fromkeys(matched):
            aspects.append({"aspect": name, "sentiment": _aspect_sentiment(score), "score": round(score, 3),
                            "confidence": round(min(0.96, 0.62 + 0.08 * len(hits)), 2), "evidence": clause,
                            "method": "semantic_taxonomy_v1", "known_aspect": True})
    clause_scores = [_clause_score(clause.casefold())[0] for clause in clauses]
    score = sum(clause_scores) / len(clause_scores) if clause_scores else 0.0
    confidence = round(min(0.95, 0.55 + 0.08 * sum(bool(_clause_score(c.casefold())[1]) for c in clauses)), 2)
    room_id = next((room for room, patterns in ROOM_PATTERNS.items() if any(re.search(pattern, clean, re.I) for pattern in patterns)), None)
    discrepancy = bool((stars is not None and stars >= 4 and score < -0.15) or (stars is not None and stars <= 2 and score > 0.15))
    return {"language": detect_language(clean), "normalized_text": clean.casefold(), "sentiment_label": _sentiment_label(score),
            "sentiment_score": round(score, 3), "confidence": confidence, "aspects": aspects, "entities": people,
            "room_id": room_id, "room_method": "explicit_text_match" if room_id else None,
            "room_confidence": 0.95 if room_id else None, "star_text_discrepancy": discrepancy,
            "analysis_status": "analyzed", "analyzer_method": "hybrid_semantic_rules",
            "analyzer_version": analyzer_version, "analyzed_at": datetime.utcnow().isoformat()}
