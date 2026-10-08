# V2.9.0 — Motor interno de eventos empresariales

## Objetivo y arquitectura

El módulo consume exclusivamente datos internos DEMO V3 y publica hechos calculados por detectores deterministas. La arquitectura de noticias externas fue retirada. El flujo es: datos → métricas → referencias → detectores → cinco gates → relevancia → deduplicación → evento.

## Catálogo implementado

### `room_revenue_change`

- Origen: Finanzas / Salas.
- Entidad: sala.
- Periodo: últimos 28 días cerrados por fecha de evaluación.
- Referencia: 28 días inmediatamente anteriores, mismo ámbito y duración.
- Evidencia mínima: 8 sesiones reservadas; configurable.
- Activación: desviación absoluta de facturación ≥18%; configurable.
- Semántica: positiva si sube, vigilancia/atención si baja.
- Resolución: deja de superar gates o umbral.
- Limitación: no determina causas ni usa periodificación como si fuera contabilidad.

### `room_cancellation_change`

- Origen: Demanda / Salas.
- Entidad: sala.
- Métrica: cancelaciones / sesiones reservadas.
- Periodo y referencia: dos ventanas consecutivas de 28 días.
- Evidencia mínima: 8 reservas.
- Activación: incremento relativo ≥35%; configurable.
- Resolución: deja de superar gates o umbral.
- Limitación: no atribuye responsabilidad a Game Masters.

## Gates y relevancia

Los gates son calidad, comparabilidad, evidencia, relevancia y duplicación. El score interno (no probabilístico) suma magnitud hasta 50 puntos, evidencia hasta 35 y actualidad hasta 15. Sirve para orden y semántica, no como probabilidad científica.

## Lifecycle

Una deduplication key estable identifica detector, sala y métrica. Reevaluaciones actualizan la incidencia activa. Al normalizarse se marca `RESOLVED`. Una reaparición crea una incidencia nueva con sufijo, conservando el histórico.

## Ejecución y resumen

El motor se ejecuta tras sincronización y mediante `POST /api/alerts/evaluate`. `GET /api/alerts/engine/status` produce el resumen y calcula el próximo resumen diario a las 09:00 `Europe/Madrid`. En local el backend debe estar ejecutándose; producción requiere un scheduler persistente del hosting.

## IA y DEMO

No se usa IA para decidir verdad, severidad o existencia. Las plantillas son deterministas. Datos DEMO V3 + algoritmo real.

## Validación

- Tests específicos del motor y alertas existentes: 21 pasados.
- Suite completa: 222 pasados.
- Coverage global: 89%; `app/alerts.py`: 94%.
- Pendiente de aceptación: auditoría visual final.
