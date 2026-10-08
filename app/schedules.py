"""Horarios operativos de referencia V2.5.

Configuración desacoplada de la visualización. En DEMO V3, al no existir un
calendario comercial histórico ni excepciones, estas franjas se consideran
ofrecidas todos los días del periodo. Una futura fuente real sustituirá esta
regla con vigencias, cierres y aperturas explícitas.
"""

REFERENCE_SCHEDULES={
    "YUCATAN":["10:30","12:30","14:30","16:30","18:30","20:30","22:30"],
    "MAGIA":["10:00","12:00","14:00","16:00","18:00","20:00","22:00"],
    "HAMMER":["09:15","11:45","14:45","17:15","19:45","22:15"],
    "SEMILLAS":["09:30","11:30","13:30","16:00","18:00","20:00","22:00"],
    "RELIQUIAS":["10:30","12:30","14:30","16:30","18:30","20:30","22:30"],
    "SOTANO":["09:30","10:30","11:30","12:30","13:30","14:30","16:00","17:00","18:00","19:00","20:00","21:00","22:00"],
    "PESADILLAS_II":["10:00","12:30","16:00","18:30","21:00"],
    "BASILISCO":["09:30","12:00","17:15","18:30","20:45"],
}

SCHEDULE_SOURCE="Horario configurado de referencia · DEMO V3"
