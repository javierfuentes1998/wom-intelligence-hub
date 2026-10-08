# Sistema visual WOM V2.2

Principio: **WOM aporta identidad; los datos aportan color**. El logotipo se carga desde el activo oficial publicado por WOM (`the-works-of-madness-logo.png`); no se fabrica un isotipo alternativo.

## Brand colors

Fondos `--brand-bg` y `--brand-bg-secondary`, superficies `--brand-surface` y `--brand-surface-elevated`, borde `--brand-border`, texto marfil `--brand-text`, texto secundario `--brand-muted` y rojo corporativo `--brand-accent`. Se usan para estructura, navegación, jerarquía, foco y acciones de marca; nunca para identificar indiscriminadamente todas las series.

## Metric colors

Cada métrica conserva un token estable: ingresos esmeralda, gastos coral, beneficio azul, margen violeta azulado, reservas violeta, sesiones naranja, clientes turquesa, cancelaciones rosa, ticket medio dorado, ocupación celeste y forecast índigo. Se aplican a acentos KPI, selectores, leyendas, series, tooltips y gráficos del chat.

## Semantic colors

`--semantic-positive`, `--semantic-negative`, `--semantic-warning`, `--semantic-info`, `--semantic-neutral` y `--semantic-excellent` expresan evaluación. Son independientes del color de métrica: ingresos sigue siendo esmeralda aunque su variación negativa se muestre en rojo semántico; una bajada de gastos usa verde semántico.

Demanda conserva rojo=muy mal, amarillo=regular, verde=bien y azul=sobresaliente. Voice of Customer reserva verde para fortalezas, rojo para problemas y ámbar/gris para atención o neutralidad.

## Categorical colors

`--categorical-1` a `--categorical-8` distinguen temporalmente salas o locales dentro de una comparación. No crean una identidad permanente ni sustituyen los metric colors.

## Accesibilidad

Color, nombre, leyenda, valor y estado textual aparecen conjuntamente. Los controles exponen `aria-pressed`, los gráficos tienen nombre accesible y los estados mantienen contraste alto. El breakpoint 390 × 844 no genera overflow global.
