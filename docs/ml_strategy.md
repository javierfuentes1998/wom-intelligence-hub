# Estrategia ML

Forecast V2 compara seasonal-naive semanal (52 semanas), mediana reciente y un híbrido 55% referencia interanual ajustada por tendencia + 45% mediana reciente. Validación temporal, nunca split aleatorio; MAE, RMSE y WAPE evitan MAPE con ceros. El rango mostrado expresa dispersión entre baselines y un suelo del 8%, no un intervalo probabilístico calibrado. Un candidato ETS solo se promoverá si mejora consistentemente el backtest.

NLP usa baseline explicable por léxico/aspectos. Su score es intensidad de regla, no probabilidad. Un transformer español futuro requiere conjunto anotado, validación por aspecto, calibración y funcionamiento offline documentado.

Cada agregado NLP conserva las reseñas originales que lo sustentan; la interfaz permite abrir evidencia por aspecto. Las cláusulas separadas por contraste permiten sentimientos distintos dentro de una reseña.
