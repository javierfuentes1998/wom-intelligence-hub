# Modelo relacional

| Tabla | PK | Granularidad | Relaciones |
|---|---|---|---|
| dim_location | id estable | un local | 1:N salas/gastos |
| dim_room | id estable | una sala | N:1 local; 1:N sesiones/reseñas |
| dim_game_master | id interno | un trabajador | 1:N sesiones |
| dim_expense_category | id | una categoría | 1:N gastos |
| fact_session | id | un slot de una sala | FK sala y GM |
| fact_expense | UUID | un cargo contabilizado | FK opcionales local/sala |
| fact_review | id | una reseña original | FK opcionales local/sala |
| dim_game_master_rate | id | una tarifa durante una vigencia | FK local y sala opcional |
| room_schedule | id | una hora ofertable por sala/día/vigencia | FK sala/temporada |
| dim_season | id | campaña con rango temporal | 1:N horarios/configuración |
| recurring_expense_plan | UUID | una versión temporal del plan | materializa fact_expense |
| insight_alert | UUID | una alerta auditable | visto/no visto |
| data_source | id | estado de una integración | sincronización y errores |

Una sesión disponible constituye el denominador fiable de ocupación y RevPAS. `room_id` y `location_id` opcionales modelan gastos globales/de local. Anular preserva trazabilidad. No se almacenan datos personales de clientes.

Una sala conserva ID estable aunque cambie de sede; la relación histórica debe resolverse mediante vigencia al importar datos reales. V2 mantiene la FK actual y prepara campos fuente; antes de una mudanza real se añadirá una tabla de asignación temporal para no reescribir el pasado.
