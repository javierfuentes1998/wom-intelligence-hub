# Motor de alertas

`evaluate_alerts` compara ventanas de 28 días con la ventana inmediatamente anterior dentro de la misma sala. Exige al menos ocho reservas. La clave `ámbito:métrica` deduplica.

Cada alerta conserva `ACTIVE/RESOLVED`, vista, detección, última evaluación, resolución, valor actual, referencia, desviación, fuerza de evidencia, relevancia y evidencia JSON. La relevancia (0–100) combina magnitud, tamaño de muestra y frescura. La severidad puede cambiar; al desaparecer la señal se registra la resolución en vez de borrar el historial. No se afirma causalidad.
