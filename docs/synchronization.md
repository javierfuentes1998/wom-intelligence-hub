# Sincronización

`sync_source(source_id)` implementa el recorrido `raw → validation → processed → gold → analytics → alerts → forecast → logs`. El adaptador normalizado usa `(source_system, external_id)` para crear o actualizar reservas, incluidas cancelaciones y cambios de GM, de forma idempotente.

Cada fuente declara intervalo esperado, estrategia, última sincronización, registros, errores y frescura. La sincronización es manual/incremental; no existe sondeo agresivo. El endpoint de demo es `POST /api/data-sources/{id}/sync`.

## Futura fuente operacional

La aplicación operacional de la empresa es código propio desplegado en Railway. Se desconocen todavía su repositorio, stack, almacenamiento, esquema, API y credenciales. El conector permanece desacoplado y pendiente de inspección técnica; no se inventa ni se intenta una integración real.
