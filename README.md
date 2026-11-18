# CaféScore · Intelligence for Location Decisions

*Inteligencia geoespacial para la expansión de Cereza Café.* Aplicación del proyecto final de Minería de Datos (ADMI 2559),
construida sobre la **plantilla oficial del curso**. Responde: **¿en qué zonas de Bogotá vale la pena hacer estudios de campo
para buscar local para las dos tiendas de 2027?**

`python check.py` → **LISTO PARA DESPLEGAR** (verificado con las versiones de `requirements.txt`).

## Qué hace la app

| Página | Qué responde |
|---|---|
| Resumen ejecutivo | Mapa de Bogotá con las 4 clases (Oportunidad, Saturada, En equilibrio, Sin demanda) o el Índice de Sobremesa Urbana; top 5, recomendación y memo descargable |
| Explorador geográfico | Clic en el mapa, coordenadas o estación de TransMilenio → razones en lenguaje de negocio, distancia en metros a Chapinero, Teusaquillo y Usaquén, riesgo y ficha descargable. 10 capas |
| Ranking de oportunidades | Top 10 con filtro de presupuesto de arriendo y otros filtros; comparador de zonas |
| Plan de estudio de campo | Cuántas zonas estudiar, costo y probabilidad de hallar 2 zonas aptas |
| Modelo vs. regla simple | Costo de errores con IC 95 %, matriz de confusión, simulador de costos, errores, SHAP, validación y valor |
| Evaluar una zona nueva | Formulario de la plantilla: escribir los datos de un sitio y evaluarlo con la zona fija |
| Metodología y riesgos | Clases, supuestos, limitaciones, ficha del modelo, fuentes y licencias |

El filtro de **presupuesto de arriendo** está en la barra lateral y aplica a todas las páginas.

## Estructura (plantilla del curso + interfaz de CaféScore)

```text
app.py                  ZONA LIBRE: interfaz (usa core/ y mi_app.py; muestra el pie de página)
mi_app.py               título, cliente, descripción, unidad y pie de página (PASO 4)
core/                   ZONA FIJA (sin cambios): cargar modelo, validar, predecir, decidir y explicar
exportar.py             ZONA FIJA: exporta el modelo a model/
desplegar.py            ZONA FIJA: instala, revisa, abre la app y guía la publicación
check.py                revisión oficial → LISTO PARA DESPLEGAR
web/index.html          opción HTML de la plantilla (no se usa: INTERFAZ = "streamlit")
model/                  pipeline.joblib, metadata.json, ejemplo_entrada.csv, resultados.csv   ← exportar.py
                        zonas.csv.gz, metricas.json, app.json                               ← resultados para la interfaz
cafescore/              módulos de la interfaz (mapas, gráficos, ranking, simulador, reportes, páginas)
pipeline/build_artifacts.py   reproduce el cuaderno y llama a exportar() (se corre una vez, con los datos del curso)
tests/                  23 pruebas (python -m pytest -q)
docs/                   guía de la plantilla, ficha del modelo, auditoría y pendientes
```

## Abrir la app en su computador

```bash
pip install -r requirements.txt
streamlit run app.py
```

O, como pide la plantilla: `python desplegar.py` (instala, corre `check.py`, abre la app y explica cómo publicarla).

## Publicar en Streamlit Community Cloud

1. Suban el contenido de esta carpeta a su repositorio **privado** de GitHub (compartido con el profesor). No lleva `cafescore_data.csv`.
2. En share.streamlit.io → *Create app* → su repositorio, rama `main`, archivo `app.py`.
3. En *Advanced settings* elijan **Python 3.13** (la versión con que se exportó el modelo).
4. La dirección que les da es la que entregan.

## Regenerar el modelo

```bash
python pipeline/build_artifacts.py --datos /ruta/cafescore_data.csv [--aperturas /ruta/aperturas.csv]
```

Reproduce la Entrega 1 (semilla 2559; se detiene si los costos de prueba no coinciden con el informe), calcula puntajes
fuera de bloque, conteo, brecha, clases, incertidumbre e índice de sobremesa, y exporta con `exportar()` de la plantilla.
