# Diccionario de datos

IDs son `VARCHAR` estables; fechas empresariales son `DATE`; instantes de sesión son `DATETIME` en hora de negocio Europe/Madrid; importes son EUR (en producción se recomienda `NUMERIC(12,2)`). `revenue` admite negativos para devoluciones; `expense.amount` debe ser positivo y `voided` anula. `rating` admite nulo y, al importar, debe validarse en [1,5]. Texto original de reseña es inmutable; `processed_text`, sentimiento, score heurístico y temas son derivados.

RAW se conserva sin cambios; PROCESSED tipa, normaliza y reporta errores; GOLD publica datasets por finanzas, demanda, salas, GM, NLP, forecast y anomalías. Las importaciones deben tener `source_batch_id` e idempotencia antes de datos reales.

`requires_double_gm` expresa la necesidad operativa; `double_gm_source` distingue `CONFIRMED` de `INFERRED`. `second_game_master_id` conserva el segundo profesional. Tarifas y planes usan `valid_from/valid_to`; cambiar una condición crea una nueva vigencia, nunca modifica historia materializada.
