# V2.7.1 — Análisis de reseñas para presentación

La fuente activa se selecciona únicamente mediante configuración:

```env
WOM_REVIEWS_SOURCE=demo
```

Para una futura activación de Google Business Profile:

```env
WOM_REVIEWS_SOURCE=google_business_profile
```

## Regeneración reproducible

Desde la raíz de `intelligence_hub`, ejecutar:

```powershell
.\.venv\Scripts\python.exe -m app.demo_reviews --count 720 --seed 2701
```

El comando elimina exclusivamente las filas con `raw_review.source = 'demo'`,
regenera el corpus con la seed indicada, ejecuta el analizador real, reconstruye
el agregado Gold y persiste el snapshot `demo:company`. No modifica las reseñas
Google, las tablas DEMO heredadas ni los datos de otros módulos.

## Garantía de transparencia

Los textos son sintéticos y reproducibles. Los resultados no están precalculados:

`RAW → PROCESSED → NLP → GOLD → dashboard → evidencia`

La integración Google, OAuth y el mapeo de ubicaciones permanecen preparados,
pero no se presentan como conectados mientras la fuente activa sea `demo`.
