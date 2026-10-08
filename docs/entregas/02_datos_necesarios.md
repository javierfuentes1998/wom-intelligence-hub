# Entrega 2 · Datos necesarios

## Criterio de procedencia

La aplicación separa datos DEMO sintéticos de lógica analítica implementada. El seed utiliza la semilla `20260929`, genera histórico reproducible y las cuatro ubicaciones objetivo. El futuro sistema WOM no se describe como conectado: se desconoce su tecnología, esquema, API, permisos y autenticación.

## Datasets y campos auditados

| Dataset | Finalidad y granularidad | Campos principales verificables | Origen actual / futuro |
|---|---|---|---|
| Reservas y sesiones | Una sesión de una sala | `id`, `room_id`, `game_master_id`, `second_game_master_id`, `starts_at`, `status`, `available`, `customers`, `revenue`, `external_id`, `source_system`, `source_updated_at`, pagos, descuentos y `requires_double_gm` | DEMO; booking/WOM por conector |
| Sesiones ofrecidas | Denominador de demanda y ocupación | `room_id`, día, `start_time`, vigencia y temporada en `room_schedule` | Horarios DEMO; calendario real pendiente |
| Gastos | Cargo puntual contabilizado | `id`, `concept`, `category_id`, `amount`, `expense_date`, `location_id`, `room_id`, `recurring`, `periodicity`, `recurrence_key`, `notes`, `voided` | DEMO/manual; WOM o archivo futuro |
| Planes recurrentes | Regla que materializa gastos | `id`, concepto, categoría, importe, ámbito, periodicidad, `valid_from`, `valid_to`, `active` | DEMO/manual |
| Reseñas | Valoración y texto auditable | RAW: identificador externo, local Google, autor visible, estrellas, comentario, fechas, respuesta, URL, hash y payload; Processed: idioma, texto normalizado, sentimiento, confianza, aspectos, entidades y sala | Corpus DEMO; Google Business Profile preparado |
| Game Masters | Dimensión de identidad y estado | `id`, `display_name`, vigencia, local principal, activo, externo | DEMO; fuente autorizada futura |
| Locales | Dimensión de sede | `id`, nombre, dirección, ciudad, activo, fuente y externo | DEMO; maestro WOM futuro |
| Salas | Dimensión de experiencia | `id`, `location_id`, nombre, capacidad, experiencia, activo, fuente y externo | DEMO; maestro WOM futuro |
| Tarifas GM | Importe por ámbito y vigencia | local, sala opcional, importe, tipo, `valid_from`, `valid_to`, notas y activo | DEMO/manual; configuración futura |
| Horarios | Slot ofertable por sala, día y vigencia | sala, `weekday`, `start_time`, fechas de vigencia y temporada | Configuración DEMO; Administración futura |

No se añaden `hora_fin`, `motivo_no_disponibilidad` ni `fecha_fin` generalizados. Cuando el modelo contiene una fecha final opcional, pertenece a la vigencia concreta de una tarifa, plan, horario o entidad.

## Calidad, privacidad y restricciones

Los identificadores internos son PK estables; las relaciones utilizan FK. `external_id`, `source_updated_at`, `imported_at` y hashes permiten rastrear origen e idempotencia. Se validan tipos, rangos positivos de importes y coherencia de periodicidad: un gasto recurrente exige periodicidad y `recurrence_key`.

La ocupación solo utiliza sesiones ofrecidas conocidas. `—` representa excepción explícita de no disponibilidad y `0` una sesión ofrecida sin reserva.

Las reseñas pueden contener nombres, texto y valoración; los nombres de Game Masters son datos personales/profesionales y no deben convertirse en temas ni rankings. Se debe minimizar el texto almacenado, restringir acceso y conservar solo la evidencia necesaria. Los jugadores atendidos no equivalen a productividad ni calidad individual.

El sistema no necesita PII de clientes para sus KPI. La futura conexión debe definir retención, permisos, cifrado, auditoría de accesos y base jurídica antes de producción.

## Actualización y fallback

DEMO se puede importar selectivamente y de forma idempotente. CSV/XLSX dispone de lectura, detección y vista previa, pero exige confirmar el mapping. Base de datos, API y booking son contratos, no conexiones simuladas. Si una fuente real no está configurada, el sistema declara el estado pendiente en lugar de mezclar silenciosamente datos.
