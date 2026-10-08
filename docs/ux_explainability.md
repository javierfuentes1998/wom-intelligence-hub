# Estándar de comprensión autónoma

El WOM Intelligence Hub debe explicarse a sí mismo. Un usuario de negocio debe
comprender qué ve, para qué sirve, cómo se calcula, cómo puede interpretarlo y
qué limitaciones tiene sin necesitar conocimientos previos de analítica.

## Tres niveles de explicación

1. **Visible:** cada sección analítica incluye una frase breve que responde qué
   muestra y para qué sirve.
2. **Ayuda detallada:** `ⓘ` o un desplegable explica definición, cálculo,
   interpretación, ejemplo y limitaciones sin saturar la pantalla.
3. **Detalle contextual:** al seleccionar una celda, KPI, alerta o indicador se
   muestran sus valores, ámbito, periodo y una interpretación específica.

## Lenguaje y fórmulas

- Se prioriza lenguaje empresarial: sesión ofrecida, valor de referencia,
  predicción y valor atípico.
- La explicación natural precede a la fórmula matemática.
- Los denominadores y periodos comparados deben quedar explícitos.
- Los conceptos no triviales incluyen un ejemplo con cifras sencillas.

## Limitaciones, DEMO y datos reales

Todo resultado basado en datos DEMO, estimaciones, aproximaciones, muestras
pequeñas o datos incompletos debe indicarlo de forma secundaria y profesional.
La interfaz debe diferenciar qué se sabe, qué se supone y qué se desconoce.
Un dato DEMO nunca debe presentarse como dato comercial histórico real.

## Dato, interpretación y recomendación

- **Dato observado:** qué ocurrió según los registros.
- **Interpretación:** qué puede significar razonablemente, sin presentarlo como
  hecho ni atribuir causalidad.
- **Acción sugerida:** qué podría revisar el negocio, no una orden automática.

## Accesibilidad

Las ayudas deben funcionar con ratón, teclado y touch, usar controles semánticos
y atributos ARIA, conservar foco visible y no depender exclusivamente del color.

## Consistencia terminológica

El mismo concepto debe conservar nombre y fórmula entre módulos. Si existen dos
métricas distintas, deben tener nombres distintos. `0`, `—`, `Dato no disponible`,
`Datos insuficientes` y `Sin base comparable` no son intercambiables.

## Aplicación progresiva

Demanda aplica el estándar completo desde V2.5.2. Inicio, Finanzas, Locales y
Salas deberán auditarse contra este estándar en sus revisiones correspondientes,
sin reconstrucción masiva. Desde Game Masters en adelante, cada cierre debe
incluir explicación de página, secciones, KPIs, gráficos, fórmulas, ejemplos,
limitaciones, DEMO frente a real y límites de interpretación.
