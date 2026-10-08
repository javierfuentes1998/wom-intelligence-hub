# Entrega 4 · Análisis y estrategia de modelado

## De la pregunta a la decisión

El diseño sigue la secuencia Problema → Usuario → Pregunta → Análisis → Resultado → Decisión. La persona responsable no necesita una pantalla ornamental, sino saber qué ha ocurrido, con qué denominador, con qué evidencia y qué limitación debe considerar.

## Análisis descriptivo y comparativo

| Pregunta | Técnica implementada | Salida y decisión |
|---|---|---|
| ¿Cuánto ingresamos y gastamos? | Agregación por periodo, local y sala | ingresos, gastos, resultado, margen y detalle |
| ¿Cómo evoluciona el negocio? | Series temporales diarias/semanales/mensuales | valores reales o índice base 100 |
| ¿Dónde funciona mejor? | Segmentación por local/sala | ingresos, reservas, jugadores y ocupación, sin causalidad |
| ¿Cuándo existe demanda? | Cruce día-hora sobre sesiones ofrecidas | reservas/oferta, niveles y ocupación DEMO |
| ¿Qué actividad tiene cada GM? | Agregación descriptiva y tarifa vigente | sesiones normales/dobles, jugadores y remuneración estimada |
| ¿Qué expresan las reseñas? | NLP heurístico auditable | sentimiento, aspectos, entidades y evidencias |
| ¿Qué cabe esperar? | Baseline determinista | previsión semanal/mensual explicada |
| ¿Qué merece atención? | Detectores por reglas y gates | eventos con referencia, muestra y lifecycle |

## Demanda

El algoritmo utiliza `sesiones reservadas / sesiones ofrecidas`. Los horarios proceden de `room_schedule`, con sala, día, hora y vigencia. En empresa/local se utiliza la unión de horarios, pero una sala solo entra en una celda si ofrece esa franja.

La intensidad es determinista: 0 % sin demanda; más de 0 y menos de 25 % baja; 25 % a menos de 50 % media; 50 % a menos de 100 % alta; 100 % máxima. Ocupación es el porcentaje exacto. Sin calendario comercial histórico real, DEMO considera configurados todos los días y no demuestra disponibilidad real.

## Game Masters

El análisis es descriptivo. La tarifa se selecciona por local/sala, tipo y vigencia. El Sótano admite dobles; en DEMO pueden inferirse por proximidad temporal de hasta 90 minutos. Es una inferencia reproducible, no una confirmación operacional. La remuneración estimada coincide con la suma del desglose de sesiones cuando todas tienen tarifa. No es nómina ni productividad.

## NLP de reseñas

Entrada: texto, estrellas, local y catálogo de Game Masters. Proceso: normalización Unicode, detección lingüística, división en cláusulas, léxico positivo/negativo, negación, aspectos contextuales, entidades y coincidencia explícita de sala. Salida: etiqueta y score de sentimiento, confianza heurística, aspectos con evidencia, personas candidatas y discrepancia estrella-texto.

La taxonomía `experiencia_grupo` exige contexto; no basta una palabra aislada. Los GMs son entidades, nunca temas. Fortalezas y problemas usan umbrales de evidencia: 0–2 insuficiente, 3–7 baja, 8–19 moderada y 20 o más sólida. Un problema recurrente exige al menos tres menciones negativas. No se declaran accuracy, precision, recall o F1 porque no existe corpus etiquetado de validación.

El pipeline DEMO es real como proceso; la fuente activa sigue siendo DEMO. Google Business Profile está preparada con OAuth oficial, pero pendiente de autorización.

## Predicciones y leakage

La predicción semanal es `0,5 × mismo periodo del año anterior + 0,5 × semana completa anterior`. La mensual es `0,7 × mismo mes del año anterior + 0,3 × mes completo anterior`. Se excluye el periodo parcial disponible y se eligen semanas lunes-domingo o meses naturales posteriores.

Es un baseline determinista, adecuado para un MVP porque es interpretable y auditable. Conserva precisión interna, redondea la presentación comercial y reconcilia reservas visibles por asignación de restos mayores.

La protección contra leakage exige que cada corte use únicamente periodos cerrados anteriores a la fecha de predicción. El código implementa esa exclusión; no existe un sistema completo de backtesting histórico ni intervalos probabilísticos. Modelos futuros podrían incluir regresión, modelos de series temporales o boosting, pero no están implementados.

## Alertas / Insights

El motor genera candidatos por sala para cambios de facturación y cancelaciones en ventanas consecutivas de 28 días. Aplica cinco gates: calidad, comparabilidad, evidencia mínima, relevancia y duplicación. La relevancia combina magnitud, tamaño de muestra y actualidad; sirve para ordenar, no es probabilidad.

Una anomalía no equivale a un problema. El motor puede clasificar una evolución positiva, atención o vigilancia, pero no conoce la causa. La clave estable deduplica reevaluaciones; una incidencia normalizada pasa a `RESOLVED` y una reaparición conserva histórico con nueva clave.

## WOM 3000

La entrada es lenguaje natural. Un router local selecciona herramientas permitidas de ingresos, gastos, reservas, ocupación, salas, locales, Game Masters, reseñas, predicción y alertas. La herramienta consulta el ORM en solo lectura y devuelve datos estructurados; después se redacta la respuesta. Un LLM opcional solo clasifica intención dentro de una lista cerrada. Si no está disponible, funciona el fallback determinista. No admite SQL ni escritura.

## Validación, DEMO y límites

La suite del repositorio documenta 259 tests superados y 89 % de cobertura global en la última validación registrada. El entorno de esta auditoría no tenía `pytest` instalable para relanzarla. Las pruebas cubren reglas de demanda, finanzas, Game Masters, reseñas, predicciones, alertas, datos e interacción API.

La generación DEMO permite desarrollar, probar y reproducir resultados sin depender de WOM. Las cifras DEMO no son resultados empresariales reales. Antes de producción quedan autenticación completa, autorización por endpoint, conectores reales, calendario comercial histórico, validación estadística, migraciones versionadas, revisión RGPD y E2E automatizado.
