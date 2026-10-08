# V2.7.2 · cierre de Análisis de reseñas

La fuente activa continúa siendo el corpus DEMO reproducible (720 reseñas, seed 2701). El pipeline y los agregados son reales; Google Business Profile permanece preparado y pendiente de autorización, sin mezclar datos.

## Taxonomía de experiencia en grupo

La regla V1 aceptaba `grupo`, `personas`, `players` y `group size` sin contexto. La versión 1.1.0 usa `experiencia_grupo` y exige contexto de recomendación/adecuación, disfrute compartido, dinámica, tamaño o experiencia jugando en grupo. Una palabra aislada no activa el aspecto.

## Evidencia y denominadores

- Insuficiente: 0–2 menciones.
- Baja: 3–7 menciones.
- Moderada: 8–19 menciones.
- Sólida: 20 o más menciones.
- Sentimiento: reseñas con texto analizable.
- Valoración: reseñas con estrellas.
- Aspectos: menciones del propio aspecto; una reseña puede aportar varios.
- Tasas locales: reseñas con texto del local dentro del periodo filtrado.

Un problema recurrente requiere al menos tres menciones negativas. Una señal positiva o negativa aislada se describe como insuficiente y no como conclusión consolidada.

## Evolución

Semana y mes se desglosan por día; año por mes. Un periodo personalizado usa día hasta 31 días, semana hasta 180 y mes para duraciones mayores. Los buckets vacíos muestran cero/sin dato y nunca se interpolan. El usuario puede alternar Volumen, Valoración y Sentimiento positivo sin mezclar escalas.

La confianza media pertenece a calidad/trazabilidad. Resume la fuerza de las señales lingüísticas activadas; no es una probabilidad de acierto ni una precisión estadística validada.
