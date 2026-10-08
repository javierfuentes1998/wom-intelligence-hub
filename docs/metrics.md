# Métricas

- Beneficio = ingresos − gastos.
- Margen = beneficio / ingresos; con ingresos cero se muestra «Dato no disponible».
- Ticket medio = ingresos / clientes.
- Ocupación = sesiones completadas / slots disponibles.
- RevPAS = ingresos / sesiones disponibles; solo se calcula si los slots son fiables.
- Comparación: mismo número de días inmediatamente anterior; los periodos parciales se comparan con igual longitud.
- Room Health Score (experimental): 25% tendencia de ingresos, 25% ocupación, 20% valoración, 20% sentimiento, 10% ausencia de cancelaciones. Pesos configurables, no científicamente validados.

## Demanda contextual

Una franja se compara con la mediana de observaciones de la misma sala, sede, día, hora y temporada. Se requieren al menos 8 comparables. Ratio frente a mediana: `<0,60` muy mal/rojo; `0,60–0,89` regular/amarillo; `0,90–1,24` bien/verde; `≥1,25` sobresaliente/azul. Son bandas operativas transparentes configurables, no juicios absolutos; sin muestra suficiente se muestra «Dato insuficiente».

Semana significa lunes–domingo. Mes conserva detalle diario/semanal y año se agrega enero–diciembre. Comparaciones: periodo inmediatamente anterior de igual duración y mismo periodo del año anterior.
