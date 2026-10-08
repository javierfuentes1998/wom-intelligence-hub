# Gestión de Datos V3.0.0

## Objetivo y alcance

Gestión de Datos permite elegir una fuente, marcar datasets y ejecutar una importación selectiva. La interfaz oculta la complejidad RAW → validación → Processed → Gold → dependencias → Alert Engine.

> Gestión de Datos V3.0.0 demuestra mediante conectores funcionales el proceso de incorporación selectiva de datos al Intelligence Hub. La integración directa con el sistema operacional de WOM queda preparada arquitectónicamente, pero no se implementa ni se simula como real al no disponer todavía de información suficiente sobre su API, base de datos y esquema.

## Fuentes y capacidades

- DEMO V3: funcional e idempotente para los nueve datasets.
- CSV/XLSX: lectura, detección de columnas, encoding, delimitador, fechas y decimales ya funcionales; la importación exige confirmar mapping.
- Sistema WOM: pendiente de configurar; no afirma conexión ni mecanismo técnico.

Cada fuente declara capacidades. Los datasets no disponibles quedan deshabilitados. Un futuro conector solo debe traducir su esquema al contrato canónico.

## Contrato canónico

Los datasets son reservas/sesiones, disponibilidad, gastos, reseñas, Game Masters, locales, salas, tarifas GM y horarios. No se importan KPIs, sentimiento, predicciones ni alertas: se calculan internamente.

## Importación e idempotencia

`POST /api/data-management/import` recibe únicamente fuente y datasets. La importación DEMO consulta los registros persistidos sin recrearlos, valida capacidades, registra una ejecución y devuelve procesados, nuevos, actualizados, sin cambios y errores. Repetirla no duplica registros.

## Dependencias

Cada dataset declara los análisis afectados. Reservas actualiza Inicio, Finanzas, Locales, Salas, Demanda, Game Masters y Predicciones; reseñas actualiza su Gold/NLP; gastos afecta Finanzas y Locales. El Alert Engine se evalúa inmediatamente para datasets relevantes.

## Gastos manuales

Se conservan los endpoints y modelos existentes para gastos puntuales y planes recurrentes. Las recurrencias se almacenan como reglas y se materializan para el periodo solicitado; no se generan infinitamente.

## Procedencia y futura conexión WOM

La fuente se registra en cada ejecución. DEMO y real no deben mezclarse silenciosamente. Para implementar WOM real se necesita conocer mecanismo de acceso, autenticación, esquema, identificadores, relaciones, permisos y semántica de estados.

## Validación

Los tests cubren capacidades, selección parcial, fuente inexistente, dataset no disponible, WOM no configurado, API, historial e idempotencia DEMO, además de CSV/XLSX existentes.
