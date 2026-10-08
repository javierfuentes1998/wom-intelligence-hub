# Finanzas V2.2.3

## Exploración de detalle V2.3.0

Los detalles de ingresos/sesiones y gastos se solicitan al backend al abrir cada bloque. El backend aplica búsqueda, filtros y una whitelist de ordenación sobre el dataset completo antes de paginar; devuelve `items`, `total`, `filtered_total`, `page`, `page_size`, `pages`, `sort`, `direction` y opciones contextuales.

Los filtros internos se combinan con periodo, local y sala globales. Cambiar un filtro o tamaño reinicia la página a 1. El drill-down de categorías abre Detalle de gastos, aplica la categoría y utiliza el mismo motor. “Limpiar filtros” no altera los filtros globales.

Finanzas abre en **Periodificados**, una lectura analítica que distribuye únicamente los gastos mensuales recurrentes dentro del mes. No cambia fechas, importes ni registros persistidos. **Contables** conserva la trazabilidad por fecha real, incluido el pico DEMO de 32.000 € del 1 de septiembre de 2026 y su anotación.

El resultado periodificado diario se define como ingresos diarios menos gastos periodificados diarios. Indica cobertura analítica de costes, no beneficio contable diario definitivo. La salida estructurada conserva fecha, resultado y `costs_covered` para futuros insights.

## Tarifa GM y nómina

Las tarifas confirmadas por sesión GM son: Altozano 18 €, República Argentina / La Florida 20 €, Los Ángeles 20 € y Orihuela 25 €. Las sesiones dobles de El Sótano usan 26 € por cada GM. Son costes laborales por sesión y no recalculan la categoría contable Nóminas.

`Nóminas LOS_ANGELES` (5.900 € en septiembre de 2026) nace en `app/seed.py`, dentro de los planes DEMO mensuales: `5200 + índice_de_sede * 350`. Es un gasto sintético fijo, materializado desde `RecurringExpensePlan`, independiente del número de sesiones y de `GameMasterRate`. Se mantiene como DEMO, no como nómina real de WOM.

## Presentación y trazabilidad

Los IDs internos permanecen estables, pero la interfaz usa nombres humanos: República Argentina / La Florida, Altozano, Los Ángeles y Orihuela. La navegación permite KPI → agregado → sede/categoría → registro. Los costes compartidos no se distribuyen entre salas sin regla explícita.

## Configuración y procedencia

La arquitectura distingue datos automáticos (Sistema WOM/booking/API futura), configuración manual (gastos, categorías, tarifas, temporadas, reglas y futuros objetivos), calculados por Intelligence Hub y DEMO. Tarifas, planes recurrentes, horarios y temporadas incluyen vigencia para no sobrescribir historia. Las categorías de gasto son configurables.

La evolución futura debe incorporar procedencia y vigencia en objetivos manuales, y conectores autorizados para precios comerciales y slots reservables. Horario comercial y disponibilidad real de sala son conceptos distintos. No se implementa scraping frágil.
