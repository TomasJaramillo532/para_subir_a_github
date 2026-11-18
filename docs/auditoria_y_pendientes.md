# Auditoría, registro de cambios y pendientes

Fecha: 16 de noviembre de 2026 · Versión de artefactos: `2026-11-final-v1`

## 1. Insumos revisados

| Insumo | Estado | Observación |
|---|---|---|
| Brief_CafeScore.docx | Leído completo | Requisitos de producto, modelado, evaluación, despliegue, entrega y condiciones de datos |
| Informe Entrega 1 (PDF, 8 págs.) | Leído completo | Metodología y cifras de prueba usadas como referencia de verificación |
| Cuaderno Cafe_Entrega1 (95 celdas) | Leído completo (código y salidas) | Ver hallazgos 3–6 |
| cafescore_data.csv | Usado solo en local | 3.275 × 33. **No se publica** |
| Diccionario_datos.xlsx | **Archivo equivocado** | Corresponde a otro caso (GlowUp, importadores). Se usó el diccionario del anexo del brief |
| Plantilla del profesor (plantilla_app.zip) | **Integrada** (16-nov, noche) | Zona fija sin cambios; ver docs/integracion_plantilla.md |
| Archivo de aperturas abril–septiembre 2026 | **No disponible** | Módulo de validación preparado, sin resultados |

## 2. Hallazgos que el equipo debe conocer antes de la entrega final

1. **La reproducción coincide con el informe de la Entrega 1.** Con semilla 2559, los seis costos en prueba (11.820, 8.460, 7.400, 6.140, 6.080 y 5.880) y el IC de la diferencia logística − regla [−800; +220] se reproducen exactamente.
2. **Inconsistencia en el informe de la Entrega 1 sobre el árbol.** El texto dice "profundidad 3, hoja mínima 50, umbral 0,20", pero la fila del árbol en la tabla (357 zonas, 22 FN, 238 FP, costo 6.080) corresponde a **profundidad 2, hoja 10, umbral 0,07**, como también dice la nota de la celda 70 del cuaderno. Las salidas impresas de las celdas 54–55 vienen de otra ejecución.
3. **La celda 7.7 del cuaderno está vacía** (modelo de conteo, brecha, clasificación y arriendo): quedaron salidas pero no el código. Por eso el cuaderno no corre de principio a fin (la celda 7.8 depende de `modelo_conteo_final`). Las clases de esa salida (52 oportunidades) no se pueden reproducir y **no se usaron**.
4. **El arriendo de la celda 7.7 (~0,9 M COP/mes por 80 m²) es incompatible** con el dato del brief (6,5 M en Chapinero Central). No se reutilizó.
5. **La selección de ensambles depende de la versión de scikit-learn.** En esta ejecución (scikit-learn 1.9.1) los mejores ensambles por costo en CV fueron bosque (n = 400, prof = 8, hoja = 10; CV 19.820) y boosting (n = 200, lr = 0,05, prof = 2, hoja = 15; CV 19.880), distintos de los impresos en el cuaderno. Los costos de la logística y el árbol en prueba no cambian. **Recomendación:** fijar la versión de scikit-learn en Colab y usar en el informe final las cifras de `data/metricas.json`.
6. **Gradient boosting es el único método que supera a la regla con evidencia en prueba** (5.580 vs 6.140; diferencia −560, IC [−1.100; −120]), pero en CV dentro de entrenamiento costó más que la logística (19.880 vs 19.720). Con la regla del equipo (elegir con entrenamiento) se mantiene la logística. La app lo explica; cambiar de modelo por el resultado en prueba sería usar la prueba para elegir.
7. **El "índice de sobremesa urbana"** del resumen ejecutivo de la Entrega 1 no tiene fórmula operativa en el cuaderno. El brief pide expresar la recomendación del memo en esos términos: falta definirlo y calcularlo antes de mostrarlo en la app.

## 3. Decisiones tomadas en esta versión (propuesta v1, pendientes de validación)

| Decisión | Valor | Dónde se cambia |
|---|---|---|
| Puntaje del mapa | Probabilidad fuera de bloque (GroupKFold 5 sobre 108 bloques) de la logística elegida | `pipeline/build_artifacts.py` |
| Modelo de conteo | Regresión de Poisson (alpha = 1,0), elegida por devianza en CV por bloques | ídem |
| Clases | Saturada: brecha ≤ −1 · Sin demanda: puntaje < 0,25 · Oportunidad: puntaje ≥ 0,25 y brecha ≥ +1 · En equilibrio: resto | `SUPUESTOS["clasificacion"]` |
| Arriendo de referencia | 6,5 M × suelo / mediana del suelo a 800 m de la tienda de Chapinero | `SUPUESTOS["arriendo"]` |
| Canibalización | 1.000 m en línea recta (ajustable en la app) | `SUPUESTOS["canibalizacion"]` |
| Ranking | Oportunidad, arriendo ≤ 12 M, fuera del radio, orden por brecha y puntaje, separación ≥ 600 m | `SUPUESTOS["ranking"]` |
| Valor del mapa | Estudios esperados para hallar 2 zonas aptas = 2 / precisión en prueba; IC por bootstrap de bloques | `build_artifacts.py` |

**Hallazgo del supuesto de arriendo:** con el ancla de Chapinero Central, 3.267 de 3.275 zonas quedan bajo 12 M. El presupuesto casi no restringe; la restricción real será la oferta de locales.

## 3 bis. Versión 2 (16-nov, tarde)

| Nuevo | Cómo se obtiene | Estado |
|---|---|---|
| Intervalo del puntaje y estabilidad de la clase por zona | 100 remuestreos de bloques en cada pliegue fuera de bloque (clasificador + conteo reentrenados) | Resultado real |
| Riesgo de la recomendación (Bajo/Medio/Alto) | Puntos por estabilidad, incertidumbre, arriendo, competencia, cercanía y oferta sin verificar | Propuesta v1 |
| Índice de sobremesa urbana | Promedio de percentiles de oficinas, universidades y espacios de permanencia a 300 m (concepto de la Entrega 1) | Propuesta v1 · AUC sola 0,77 |
| Simulador de costos FN/FP | Umbral y cortes re-elegidos en entrenamiento; prueba con las mismas 1.000 muestras de bloques | Reproduce exactamente la tabla oficial con 60/20 |
| Errores por tipo de zona y suelo; calibración | Zonas de prueba / puntajes fuera de bloque | Resultado real |
| Plan de estudio de campo | Precisión en prueba con IC → binomial; escenario con supuestos del brief (margen 15 M, adecuación 250 M) | Escenario, no proyección |
| Memo de una página y ficha de zona | HTML imprimible generado desde los artefactos | Listo |

## 4. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Mapa real de Bogotá con sus celdas | ✅ (mapa base CARTO; verificar carga en la URL pública) |
| Puntajes y clasificaciones justificadas | ✅ (clases como propuesta v1) |
| Selección de zona en el mapa | ✅ probado con clic en navegador |
| Consulta por coordenadas | ✅ probados: válida, fuera de Bogotá, invertidas, fuera del área |
| Distancias correctas | ✅ Haversine recalculado en pruebas |
| Filtro de arriendo con supuesto documentado | ✅ (supuesto v1) |
| Top 10 | ✅ |
| Comparación honesta con la regla | ✅ |
| Validación con aperturas recientes | ⏳ **Pendiente: falta el archivo** |
| Valor económico con supuestos y límites | ✅ |
| Sin resultados inventados | ✅ |
| Zona fija de la plantilla respetada | ✅ core/, exportar.py, desplegar.py oficiales sin cambios (huellas verificadas por check.py) |
| Datos originales no publicados | ✅ |
| Atribución | ✅ |
| Uso sin asistencia técnica | ✅ (pendiente prueba con un usuario real) |
| `check.py` → LISTO PARA DESPLEGAR | ✅ **check.py oficial** ejecutado con las versiones de requirements.txt (Streamlit 1.64.0): LISTO PARA DESPLEGAR |
| URL pública comprobada | ⏳ **Pendiente: requiere la cuenta de GitHub/Streamlit del equipo** |

## 5. Verificaciones ejecutadas

- `python -m pytest -q` → 23 pruebas superadas (v2 añade simulador, incertidumbre, riesgo y documentos) (integridad, H3, brecha, clases, distancias, arriendo, costos, reproducción, esquema, coordenadas, ranking, formato).
- `python verificar_local.py` en un entorno virtual limpio instalado solo con `requirements.txt` → superada.
- Navegador sin interfaz (Chrome): las cinco páginas cargan sin excepciones; clic en el mapa, consulta de coordenadas (4 casos), selección de fila del ranking, comparador y todas las pestañas funcionan.
- El mapa base no se pudo ver en el entorno de prueba (sin salida a internet); las capas H3 sí se dibujan.
