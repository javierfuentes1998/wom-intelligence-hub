# V2.8.0 — Cierre técnico de Predicciones

## Regla ejecutiva

- Semana: `0,5 × mismo periodo del año anterior + 0,5 × periodo inmediatamente anterior`.
- Mes: `0,7 × mismo mes del año anterior + 0,3 × mes completo inmediatamente anterior`.
- Las reservas conservan precisión interna y se muestran como unidades enteras mediante redondeo comercial.
- La facturación conserva precisión interna y se muestra como entero mediante `ROUND_HALF_UP`; por tanto `57.065,50 € → 57.066 €`.

## Alcance validado

La vista usa periodos completos, distribución temporal reconciliada con los totales, filtros de local/sala, estados de historial insuficiente, explicación de referencias y pesos, tooltips accesibles y layout responsive. La fuente visible está marcada como DEMO V3.

## Validación final

- Tests específicos V2.8.0: 32 pasados.
- Suite completa: 213 pasados.
- Coverage global: 89%; `app/predictions.py`: 98%.
- Sintaxis Python y JavaScript: correcta.
- Auditoría navegador: semana/mes, `57.066 €`, filtro Altozano, viewport 390×844, accesibilidad básica y consola sin errores/warnings.

La revisión visual final del usuario sigue siendo el único paso de aceptación antes de declarar el módulo cerrado.
