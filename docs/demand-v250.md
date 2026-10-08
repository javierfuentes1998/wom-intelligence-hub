# Demanda V2.5.0

## Horarios

La configuración canónica está en `app/schedules.py`. Es una capa de referencia sustituible por Administración, base de datos o API. Define horas por sala, pero no inventa días de apertura, festivos ni excepciones. En DEMO V3, al no existir un calendario comercial histórico, cada horario configurado se considera ofrecido todos los días del periodo salvo que exista una excepción explícita.

El seed histórico DEMO utilizaba horas genéricas. Para conservar todas las reconciliaciones económicas, el análisis proyecta esas sesiones de forma determinista y ordinal sobre las horas de referencia sin modificar reservas, jugadores, estados ni importes. Esta proyección nunca decide la oferta. Si varios registros recaen en una misma franja, se conserva su multiplicidad como oportunidades DEMO. Una integración real utilizará la hora exacta aportada por reservas.

## Semántica

- `—`: existe una excepción explícita de no disponibilidad; queda fuera del denominador.
- `0`: la sesión estaba ofrecida, pero no terminó con una reserva completada.
- `1+`: existen reservas completadas agregadas en la celda.
- Ocupación: sesiones reservadas / sesiones ofrecidas.

## Demanda contextual DEMO

La clasificación representa intensidad de utilización, no volumen absoluto. Es determinista: 0 % sin demanda; más de 0 y menos de 25 % baja; 25–menos de 50 % media; 50–menos de 100 % alta; 100 % máxima. Se calcula sobre las sesiones ofrecidas de la celda. No es un modelo predictivo ni una verdad comercial y deberá sustituirse o validarse con histórico real.

## Agregación

En sala se usan únicamente sus horas. En local y empresa se construye la unión de horas, pero cada celda solo incluye las salas cuya configuración contiene esa franja. Las salas que no ofrecen una hora no penalizan su ocupación.
