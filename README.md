# The Works of Madness Intelligence Hub

Sistema local de inteligencia empresarial y apoyo a decisiones para The Works of Madness. Centraliza finanzas, locales, salas, demanda, Game Masters, análisis de reseñas, predicciones, alertas, gestión de datos y WOM 3000. Los datos incluidos son **DEMO V3 sintéticos**; nunca representan resultados reales.

La identidad visual usa el logotipo oficial publicado por WOM y tokens `--wom-*`. Los diseños y contratos nuevos se documentan en `docs/design_system.md`, `docs/demo_scenarios.md`, `docs/alert_engine.md`, `docs/synchronization.md` y `docs/llm_analytics.md`.

## Arranque en Windows PowerShell

```powershell
cd "C:\Users\javie\Documents\Codex\2026-07-22\ex\outputs\Ia Generativa\intelligence_hub"
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start.ps1
```

Abrir http://127.0.0.1:8000. Swagger: http://127.0.0.1:8000/docs.

Requiere Python 3.11–3.13; el script prioriza automáticamente Python 3.13 mediante el lanzador `py`.

## Tests

```powershell
.\scripts\test.ps1
```

## Arquitectura

- `app/`: FastAPI, SQLAlchemy, servicios analíticos, temporalidad, GM, NLP, conectores y chat seguro.
- `frontend/`: SPA responsive sin build, servida por FastAPI.
- `data/raw|processed|gold`: zonas de datos; los ficheros generados se excluyen de Git.
- `tests/`: pruebas unitarias y de integración/API.
- `docs/`: decisiones técnicas y documentación del TFM.

SQLite permite una instalación inmediata; `WOM_DATABASE_URL` desacopla el motor para migrar a PostgreSQL. La capa API separa UI, dominio y persistencia. No se reconstruye ni acopla el chatbot RAG de clientes.

## Datos demo y reales

`python -m app.seed` crea tres años reproducibles (semilla `20260929`) con las cuatro sedes y ocho experiencias actualmente conocidas. Horarios, sesiones, empleados, reseñas e importes son sintéticos y visibles como DEMO. CSV/Excel disponen de detección de delimitador/encoding y vista previa; los conectores de base de datos, API y booking quedan como contratos explícitos hasta conocer la fuente real.

## Modelos y rigor

- Forecast: seasonal-naive, mediana reciente y combinación año anterior + tendencia, con backtesting temporal.
- Anomalías: mediana y MAD robusto, explicado como desviación y no como causalidad.
- NLP: baseline auditable de léxico y aspectos; el `score` es intensidad heurística, no probabilidad.
- Room Health Score: fórmula experimental, pesos visibles y configurables.
- Asistente: widget funcional sin API key mediante herramientas semánticas locales de solo lectura; un proveedor LLM futuro solo seleccionará esas herramientas.

## Limitaciones / roadmap

Datos y conclusiones son DEMO. Faltan conectores reales, calendario comercial histórico, intervalos probabilísticos calibrados, autenticación completa, autorización por endpoint, migraciones Alembic y automatización E2E con navegador empaquetado. Antes de producción: incorporar fuentes reales, acordar definiciones KPI, validar slots y dobles confirmados, calibrar modelos y realizar revisión RGPD/seguridad.

## Documentación académica

- [Ideas de producto](docs/entregas/01_ideas_producto.md)
- [Datos necesarios](docs/entregas/02_datos_necesarios.md)
- [Modelo de datos](docs/entregas/03_modelo_datos.md)
- [Análisis y modelado](docs/entregas/04_analisis_modelado.md)

La documentación distingue implementado frente a preparado para el futuro y DEMO frente a datos reales.

## Validación actual

En el entorno virtual del proyecto: 259 tests superados, 0 fallos, 0 omitidos y 89 % de cobertura global. La suite se ejecuta con `.\\scripts\\test.ps1`.

## Seguridad de configuración

`.env` está excluido por `.gitignore`; `.env.example` solo contiene placeholders y configuración local DEMO. No se incluyen secretos en este README. La credencial DEMO histórica del README anterior se ha retirado de esta portada y no debe reutilizarse en producción.

Para habilitar el usuario local `admin`, el evaluador debe definir su propia contraseña en `.env` antes de ejecutar `scripts/setup.ps1`:

```dotenv
WOM_DEMO_ADMIN_PASSWORD=establecer-una-contraseña-local
```

El valor no debe subirse a Git. Si se omite, el seed crea una credencial aleatoria que no se muestra ni se registra; en ese caso debe regenerarse la DEMO después de configurar la variable para poder acceder con `admin` cuando la autenticación esté habilitada.

Los nombres visibles de Game Masters incluidos en DEMO son identidades ficticias. Sus sesiones, tarifas y remuneraciones también son sintéticas.
