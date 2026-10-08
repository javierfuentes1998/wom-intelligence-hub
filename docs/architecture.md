# Arquitectura

Monolito modular: SPA → API REST FastAPI → servicios de dominio/analítica → SQLAlchemy → SQLite/PostgreSQL. Esta opción es defendible para un TFM y evita microservicios prematuros. La API documentada es la frontera de integración. El chatbot externo queda desacoplado.

Los estados vacíos, sin configuración y errores esperables se devuelven explícitamente. Logging registra operaciones, nunca secretos. Configuración centralizada mediante variables `WOM_*`.

## Flujo de datos V2

FUENTE → conector → RAW inmutable → validación reportada → PROCESSED tipado → GOLD orientado a consumo. `CSVConnector` y `ExcelConnector` son operativos; `DatabaseConnector`, `APIConnector` y `BookingConnector` declaran el contrato sin simular conexiones. `source_system`, `external_id`, `source_updated_at` e `imported_at` permiten UPSERT/idempotencia.

El chat está disponible como widget global. El backend interpreta localmente preguntas soportadas y devuelve datos o especificaciones `bar|line|table` validadas. Si se configura un LLM, solo podrá seleccionar herramientas de lectura; nunca recibe acceso SQL.

## Futura fuente operacional en Railway

La fuente operacional futura es una aplicación propia desplegada en Railway, no un CMS. Aún no se conocen repositorio, framework, lenguaje, base de datos, esquema, API ni credenciales. El conector queda como frontera conceptual pendiente de inspección técnica: no se presupone PostgreSQL, MySQL ni una API concreta y no se intenta ninguna conexión.
