# Explorador multivariable ejecutivo

## Objetivo

Permite analizar varias métricas sin depender del asistente: ingresos, gastos, beneficio, margen, reservas, sesiones, clientes, cancelaciones, ticket medio y ocupación.

## Temporalidad y granularidad

Reutiliza Semana, Mes, Año y Personalizado, además de Anterior, Actual y Siguiente. La regla automática es: hasta 62 días, diario; de 63 días a 730 días, mensual; más de 730 días, trimestral. Año fuerza granularidad mensual. El backend acepta también día, semana, mes o trimestre explícitos.

## Unidades y ejes

En Valores reales las series se separan automáticamente en bandas sincronizadas: euros, conteos y porcentajes. No se suman porcentajes ni promedios diarios. Margen se calcula como beneficio/ingresos, ticket medio como ingresos/jugadores y ocupación con la definición contextual vigente. En Índice base 100 todas las series comparten una banda y cada una se normaliza respecto a su primer valor no nulo y distinto de cero. La interfaz lo identifica explícitamente como índice.

## Filtros

Los filtros existentes determinan el ámbito: toda la empresa, local o sala. La selección de métricas y el modo se conservan al cambiar periodo o ámbito mediante estado de aplicación y `localStorage`.

## Arquitectura

`GET /api/analytics/timeseries` recibe `start_date`, `end_date`, `granularity`, `scope_type`, `scope_id` y parámetros repetidos `metrics`. Devuelve periodo, granularidad, ámbito, metadatos de métrica, series y totales. Toda cifra procede de sesiones y gastos del backend; el explorador no depende de Gemini.

## Estados y rendimiento

El componente cancela peticiones obsoletas, mantiene altura durante carga y muestra estados vacío y error. Selector/leyenda, tooltip por hover o tap y Restablecer comparten el mismo estado. Para más de cuatro métricas aparece una recomendación de claridad sin bloquear la exploración.

## Limitaciones

Forecast no se superpone todavía al histórico porque el modelo vigente produce horizonte semanal y el explorador admite granularidades variables. Incorporarlo exige una alineación temporal explícita para no presentar predicciones como observaciones.

## Refinamientos V2.2.1

- La carga inicial consulta `/api/data-range`: si el periodo actual está completamente después del último dato, abre el mes del último dato y lo identifica como histórico. El botón **Actual** siempre respeta el periodo actual, aunque esté vacío.
- Cada banda incorpora entre cuatro y siete ticks Y calculados con números legibles y ticks X adaptativos. En móvil se reduce la densidad temporal.
- Hover o tap sincroniza crosshair y puntos activos en todas las bandas, y muestra un tooltip flotante con índice y valor real cuando procede.
- El resumen compacto utiliza `totals` del backend; las métricas no aditivas mantienen su fórmula agregada.
- Para gastos existen dos vistas: **Contables**, fiel a la fecha del registro, y **Periodificados**, que distribuye únicamente gastos marcados como recurrentes mensuales. Esta segunda vista es analítica, conserva el total de un mes completo y no modifica ningún registro.

### Pico del 1 de septiembre de 2026

El pico contable de 32.000 € está compuesto por 16 materializaciones mensuales: nóminas (22.900 €), alquileres (8.280 €), seguros (560 €) e Internet (260 €), cuatro registros por local. Todos proceden de planes recurrentes, tienen periodicidad `monthly` y se contabilizan el primer día del mes. La vista contable conserva y anota el pico; la vista periodificada permite analizar el resto del mes sin falsear los datos originales.
