"""Reproducible DEMO review corpus that exercises the real NLP pipeline.

Only rows whose source is ``demo`` are reset. No operational or Google review
data is touched. The texts are synthetic combinations, never copied reviews.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, SessionLocal, engine
from .models import GameMaster, Location, ProcessedReview, RawReview, ReviewGoldSnapshot
from .review_nlp import content_hash
from .review_service import DEMO_SOURCE, _process, build_gold, source_config

LOCATIONS={
    "LA_FLORIDA":{"name":"República Argentina / La Florida","rooms":["El Sótano","Hammer Killer","Las Reliquias de Judy"],"signal":["Hacía demasiado calor y faltaba aire acondicionado","La temperatura fue terrible aunque la sala era genial"]},
    "ALTOZANO":{"name":"Altozano","rooms":["Yucatán","Escuela de Magia","El Veneno del Basilisco"],"signal":["La ambientación fue espectacular y la decoración increíble","Nos encantó la inmersión y la ambientación tan original"]},
    "LOS_ANGELES":{"name":"Los Ángeles","rooms":["Las Semillas de la Locura"],"signal":["Las pruebas eran demasiado fáciles aunque la historia fue genial","Los puzles fueron difíciles y muy originales"]},
    "ORIHUELA":{"name":"Orihuela","rooms":["Pesadillas II"],"signal":["Los actores estuvieron excelentes y pasamos mucho miedo","El terror y los sustos fueron espectaculares"]},
}

POSITIVE=[
    "La experiencia fue increíble y muy divertida", "La historia fue genial y totalmente inmersiva",
    "Los puzles fueron excelentes y muy originales", "La atención del equipo fue amable y excelente",
    "Las pistas llegaron justo a tiempo y nos ayudaron", "El ritmo fue genial de principio a fin",
    "La tecnología y los mecanismos fueron espectaculares", "El audio y el sonido fueron excelentes",
    "La iluminación creó una atmósfera increíble", "Todo estaba muy limpio y las instalaciones eran excelentes",
    "El precio nos pareció genial por la experiencia", "La reserva en la web fue fácil y excelente",
    "No tuvimos que esperar nada y fueron muy puntuales", "La duración fue genial para nuestro grupo",
    "La ubicación y el acceso fueron muy fáciles", "La decoración era original y la ambientación fantástica",
]
NEGATIVE=[
    "Había demasiado calor y el aire acondicionado no funcionaba", "Tuvimos mucha espera y empezaron con retraso",
    "Una prueba estaba rota y necesitaba mantenimiento", "El audio fue terrible y apenas se entendía",
    "La iluminación era mala en algunas pruebas", "El precio nos pareció caro para la duración",
    "La reserva por la web fue terrible", "Las instalaciones estaban sucias",
    "La experiencia fue demasiado corta", "La ubicación era difícil y no había parking",
    "No daba nada de miedo", "Las pruebas eran demasiado fáciles",
]
NEUTRAL=[
    "La experiencia estuvo bien", "Fuimos en grupo y terminamos a tiempo", "La duración fue la esperada",
    "Las pruebas no eran demasiado difíciles", "La sala tenía varias pruebas y una historia",
]
INTRO=["Fuimos con amigos", "Era nuestra primera visita", "Celebramos un cumpleaños", "Jugamos en familia", "Volvimos después de varios meses", "La sesión empezó por la tarde"]
ENDING=["Volveríamos sin duda", "En conjunto salimos contentos", "Fue una tarde diferente", "Lo recomendaríamos a otros grupos", "La experiencia tuvo buenos momentos", "Nos quedamos comentándola al salir"]
KNOWN_PEOPLE=["Aster", "Elar", "Bruma", "Lumera", "Hestiax", "Fionex", "Ivarn"]


def _synthetic_text(rng: random.Random, location_id: str, index: int, stars: int) -> str | None:
    if index % 16 == 0:return None
    if index % 20 == 1:
        return rng.choice(["The escape room was great and the staff were very friendly", "The puzzles were original but it was too hot inside", "Great atmosphere and an amazing story"])
    if index % 25 == 2:
        return rng.choice(["La salle était géniale et les énigmes très originales", "Nous avons adoré l'ambiance mais il faisait très chaud", "Le personnel était très aimable"])
    parts=[rng.choice(INTRO)]
    if index % 3 == 0:parts.append(rng.choice(LOCATIONS[location_id]["signal"]))
    else:parts.append(rng.choice(POSITIVE if stars>=4 else NEGATIVE if stars<=2 else NEUTRAL))
    if index % 7 == 0:parts.append("pero "+rng.choice(NEGATIVE).lower())
    elif index % 11 == 0:parts.append("y "+rng.choice(POSITIVE).lower())
    if index % 17 == 0:parts.append(f"{rng.choice(KNOWN_PEOPLE)} estuvo genial y nos ayudó justo cuando lo necesitábamos")
    if index % 53 == 0:parts.append("Nos atendió Zorik y fue majísimo")
    if index % 5 == 0:parts.insert(1,f"Jugamos {rng.choice(LOCATIONS[location_id]['rooms'])}")
    parts.append(rng.choice(ENDING))
    return ". ".join(parts)+"."


def generate_demo_reviews(db: Session, count: int=720, seed: int=2701, reset: bool=True) -> dict:
    missing=set(LOCATIONS)-set(db.scalars(select(Location.id)).all())
    if missing:raise ValueError(f"Faltan locales para generar reseñas DEMO: {sorted(missing)}")
    if reset:
        ids=select(RawReview.id).where(RawReview.source==DEMO_SOURCE)
        db.execute(delete(ProcessedReview).where(ProcessedReview.raw_review_id.in_(ids)))
        db.execute(delete(RawReview).where(RawReview.source==DEMO_SOURCE))
        db.execute(delete(ReviewGoldSnapshot).where(ReviewGoldSnapshot.scope_key.like("demo:%")))
        db.commit()
    rng=random.Random(seed);people=[x.display_name for x in db.scalars(select(GameMaster).where(GameMaster.active==True)).all()];now=datetime.now(UTC).replace(tzinfo=None)
    start=datetime(2025,1,1,10);span=(datetime(2026,9,30,22)-start).days
    location_ids=list(LOCATIONS)
    stars_population=[5]*55+[4]*25+[3]*10+[2]*6+[1]*4
    for index in range(count):
        location_id=location_ids[index%4];stars=rng.choice(stars_population);created=start+timedelta(days=round(index*span/max(1,count-1)),hours=rng.randrange(0,12))
        comment=_synthetic_text(rng,location_id,index,stars);external=f"DEMO-V271-{seed}-{index+1:04d}"
        payload={"synthetic":True,"seed":seed,"index":index+1,"location_id":location_id,"stars":stars,"comment":comment,"create_time":created.isoformat()}
        raw=RawReview(id=f"demo:{seed}:{index+1:04d}",source=DEMO_SOURCE,external_review_id=external,google_location_id=f"demo/{location_id}",
            wom_location_id=location_id,reviewer_display_name=None,star_rating=stars,comment=comment,create_time=created,update_time=created,
            reply=None,source_url=None,content_hash=content_hash(json.dumps(payload,ensure_ascii=False,sort_keys=True)),raw_payload=json.dumps(payload,ensure_ascii=False,sort_keys=True),
            ingestion_time=now,last_seen_at=now,active=True)
        db.add(raw);_process(db,raw,people)
    cfg=source_config(db,DEMO_SOURCE);cfg.status="DEMO_READY";cfg.last_success_at=now;cfg.last_error=None;cfg.received_count=count;cfg.new_count=count;cfg.modified_count=0;cfg.unchanged_count=0;cfg.error_count=0
    db.commit();gold=build_gold(db,source=DEMO_SOURCE)
    snapshot=ReviewGoldSnapshot(scope_key="demo:company",analyzer_version=settings.review_analyzer_version,payload=json.dumps(gold,ensure_ascii=False,default=str))
    existing=db.get(ReviewGoldSnapshot,"demo:company")
    if existing:existing.generated_at=now;existing.analyzer_version=settings.review_analyzer_version;existing.payload=snapshot.payload
    else:db.add(snapshot)
    db.commit()
    return {"source":DEMO_SOURCE,"seed":seed,"created":count,"locations":{x["location_id"]:x["reviews"] for x in gold["locations"]},"kpis":gold["kpis"],"analyzer":gold["analyzer"]}


def main():
    parser=argparse.ArgumentParser(description="Regenera únicamente las reseñas DEMO V2.7.1")
    parser.add_argument("--count",type=int,default=settings.review_demo_count);parser.add_argument("--seed",type=int,default=settings.review_demo_seed);parser.add_argument("--no-reset",action="store_true")
    args=parser.parse_args();Base.metadata.create_all(engine)
    with SessionLocal() as db:print(json.dumps(generate_demo_reviews(db,args.count,args.seed,not args.no_reset),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
