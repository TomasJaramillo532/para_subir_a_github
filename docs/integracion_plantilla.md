# Integración con la plantilla oficial (hecha)

- `core/`, `exportar.py`, `desplegar.py`, `check.py` y `web/index.html` son los de la plantilla, **sin cambios**
  (las huellas SHA-256 coinciden con las que verifica `check.py`).
- El modelo se exporta con `exportar()` desde `pipeline/build_artifacts.py`:
  - `modelo`: pipeline (log1p → StandardScaler → LogisticRegression C = 0,01) entrenado con los 86 bloques de entrenamiento.
  - `X_entrenamiento`: 2.543 zonas × 27 variables (23 originales + 4 construidas).
  - `umbrales = [0.25]`, `decisiones = ["Descartar por ahora", "Estudiar la zona"]`, `evento = "tener al menos un café"`.
  - `metricas`: costo del modelo 5.880, de la regla 6.140 (millones, zonas de prueba), regla escrita e intervalo del ahorro [−220; +800,5].
  - `tabla_resultados`: las 3.275 zonas con `probabilidad_resultados` = puntaje **fuera de bloque** (validación cruzada por bloques),
    `columna_id = "h3"` y columnas de clase, índice de sobremesa, brecha, arriendo de referencia y distancia.
- Las razones de cada zona en la app son las de la zona fija (`core.explicar`, guardadas en `model/resultados.csv`).
- La página «Evaluar una zona nueva» usa `core.validar` y `core.evaluar`, como el formulario de la plantilla.
- `mi_app.py` está completo (sin `COMPLETAR`) y `app.py` muestra `config["pie"]` al final.
- Streamlit queda en la versión de la plantilla (1.64.0); la interfaz se probó con ella.
