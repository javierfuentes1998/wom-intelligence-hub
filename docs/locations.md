# Locales V2.3.0

Locales responde al estado de una sede concreta. El selector persistente conserva los IDs internos (`LA_FLORIDA`, `ALTOZANO`, `LOS_ANGELES`, `ORIHUELA`) y presenta únicamente nombres humanos.

Todo KPI, serie del explorador, sala y alerta se consulta con el `location_id` seleccionado. Las alertas se relacionan con el local mediante la sala declarada en su evidencia. La variación interanual mostrada corresponde a ingresos del mismo local. El selector Sala se limita a las salas de la sede y se reinicia cuando se cambia a una sede incompatible.

Relación DEMO vigente: La Florida 3 salas, Altozano 3, Los Ángeles 1 y Orihuela 1. Inicio conserva el scope de empresa y no comparte el render de detalle de Locales. Noticias no forma parte de Locales.

La ocupación continúa calculándose sobre slots DEMO conocidos; no equivale al horario comercial real.
