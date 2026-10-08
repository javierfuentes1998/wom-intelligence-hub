# Salas V2.4.0

El detalle de sala usa el ID interno de `dim_room` como clave de navegación y mantiene el nombre humano únicamente como presentación. El periodo y los filtros globales permanecen sincronizados al cambiar entre las ocho salas DEMO.

## Alcance y reconciliación

- Ingresos, reservas y jugadores incluyen exclusivamente sesiones completadas de la sala y periodo seleccionados.
- Sesiones ofrecidas DEMO proceden del horario configurado de referencia aplicado a cada día del periodo, salvo excepciones explícitas.
- Ocupación = reservas completadas / sesiones ofrecidas de referencia.
- Ticket medio por jugador = ingresos / jugadores.
- Jugadores por reserva = jugadores / reservas completadas.
- Tasa de cancelación = canceladas / (completadas + canceladas).
- Ingreso por sesión ofrecida = ingresos / sesiones ofrecidas de referencia.
- No se calcula beneficio ni rentabilidad por sala sin costes directos completos.

## Atribución

Game Masters, reseñas, temas, evidencias y alertas se muestran solo cuando su `room_id` coincide exactamente con la sala seleccionada. Las reseñas sin sala no se reparten ni se infieren.

## Health Score experimental

Componentes V2.5: evolución de ingresos 40 %, ocupación 40 % y control de cancelaciones 20 %. La evolución se normaliza como `clamp(50 + variación porcentual × 2)`, la ocupación conserva su porcentaje y el control de cancelaciones utiliza `100 − tasa`. Los componentes disponibles se renormalizan si falta alguno. VOC ya no forma parte del detalle ni del score. El indicador es descriptivo, experimental y no representa beneficio, causalidad ni ranking.

## Procedencia y limitaciones

Los datos actuales son DEMO. La disponibilidad procede de horarios de referencia, no de un calendario comercial histórico completo. Precios, vigencias y excepciones están preparados como evolución futura, sin inventar valores. Las señales positivas de ingresos se presentan como oportunidades; los tonos críticos quedan reservados a deterioros o riesgos.
