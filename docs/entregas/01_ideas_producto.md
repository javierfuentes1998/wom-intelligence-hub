# Entrega 2 · Idea y definición del producto

## Contexto y problema

The Works of Madness gestiona varias experiencias de escape room repartidas en distintos locales. La información necesaria para decidir se encuentra conceptualmente distribuida entre reservas, sesiones, gastos, horarios, salas, Game Masters y opiniones de clientes. El problema empresarial no es la ausencia de datos, sino la dificultad de convertirlos en una lectura común, trazable y accionable.

La necesidad es disponer de una visión que permita responder cuánto se ingresa y gasta, qué resultado se observa, cuándo se concentra la demanda, cómo se comportan los locales y salas, qué actividad operativa se atribuye a los Game Masters, qué expresan las reseñas y qué señales merecen atención.

## Evolución de la idea

La documentación disponible no conserva un catálogo verificable de ideas descartadas. Por ello no se inventan alternativas históricas. La evolución que sí puede sostenerse es funcional: una necesidad inicial de resumen operativo se amplió hacia un hub de inteligencia empresarial con análisis financiero, demanda, reseñas, predicción, alertas y consulta natural.

La idea seleccionada es **The Works of Madness Intelligence Hub**: una aplicación interna que centraliza indicadores y transforma datos operativos en análisis explicables. El producto final conserva una interfaz ejecutiva, pero añade trazabilidad hasta sesiones, gastos, reseñas y evidencias.

## Usuario, necesidad y propuesta de valor

El usuario objetivo es la persona responsable de la gestión de locales y salas. Necesita comparar periodos, localizar desviaciones, entender su denominador y distinguir hechos observados de interpretaciones.

La propuesta de valor es reducir el tiempo entre dato y decisión: una misma aplicación presenta KPI, filtros temporales y organizativos, detalle trazable, explicaciones metodológicas y límites de uso. La plataforma no sustituye el criterio de gestión ni afirma causalidades que no estén en los datos.

## Producto esperado y MVP

El MVP debía ofrecer:

- resumen ejecutivo de ingresos, gastos, resultado, reservas, jugadores, ticket y ocupación;
- análisis por local y sala;
- demanda basada en sesiones ofrecidas y reservadas;
- actividad y remuneración operativa estimada de Game Masters;
- análisis auditable de reseñas;
- predicciones deterministas;
- alertas explicables;
- importación DEMO idempotente y asistente interno de solo lectura.

La aplicación actual contiene esas áreas, siempre identificando la fuente DEMO cuando corresponde.

## Viabilidad, riesgos y éxito

La viabilidad técnica se apoya en FastAPI, SQLAlchemy, SQLite por defecto, una SPA sin build complejo y conectores desacoplados. El seed DEMO es reproducible y permite probar sin depender de una fuente externa.

Los riesgos principales son la falta de acceso al sistema operativo WOM, ambigüedad de definiciones KPI, disponibilidad comercial histórica incompleta, privacidad de reseñas y nombres de empleados, inferencia de sesiones dobles, y uso excesivo de métricas como si fueran evaluaciones laborales.

Los criterios de éxito son: coherencia de cifras entre módulos, trazabilidad, separación DEMO/REAL, explicabilidad, filtros consistentes, ausencia de duplicados en importaciones repetidas, cobertura de reglas críticas y una base clara para sustituir DEMO por conectores autorizados.

## Alcance y evolución futura

El alcance actual es local y demostrable. No incluye conexión productiva al sistema WOM de Railway, calendario comercial real, autenticación y autorización completas, migraciones versionadas ni validación estadística de modelos. Esas capacidades quedan como evolución preparada, no como funcionalidades existentes.
