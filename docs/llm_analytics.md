# Capa LLM analítica

Flujo: pregunta + contexto visible + conversación → selección de herramienta permitida → consulta ORM de solo lectura → resultado estructurado → respuesta natural. Gemini se configura con `GEMINI_API_KEY` y `GEMINI_MODEL`; la clave nunca se almacena ni registra en el proyecto. Se reutiliza de forma segura la configuración local del chatbot anterior. Si falla o no existe, opera el router determinista.

Herramientas: ingresos, gastos, salas, sedes, GM, cancelaciones, reseñas y previsión. No acepta SQL ni órdenes de escritura. Los gráficos se generan exclusivamente desde la salida numérica de la herramienta.
