"""Módulo 5 — Metodología, riesgos y transparencia."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import config, data, logic, ui
from ..config import CLASES, ORDEN_CLASES


def render():
    md, m, z = data.metadata(), data.metricas(), data.zonas()
    sup = md["supuestos"]
    ui.encabezado("Módulo 5 · Metodología y transparencia", "Cómo funciona CaféScore y qué no puede decir",
                  "Para la fundadora, la analista de crédito y el comité evaluador.")

    t = st.tabs(["Cómo funciona", "Clases y supuestos", "Datos", "Limitaciones", "Ficha del modelo", "Fuentes y licencias"])

    with t[0]:
        pt = m["particion"]
        st.markdown(f"""
**Paso 1 · Perfil de demanda.** Un clasificador ({md['modelo']}, {md['parametros']}) aprende qué perfil tienen las zonas que
hoy tienen al menos un café: comercio, oficinas, universidades, transporte y valor del suelo a ~300 m. Sus {len(md['columnas'])}
variables de entrada **no incluyen** cafés, restaurantes ni nombres de negocios, para no meter el resultado en las entradas.

**Paso 2 · Oferta esperada frente a observada.** Un modelo de conteo ({m['conteo']['modelo']}) estima cuántos cafés corresponden
a ese perfil. La **brecha** es esa expectativa menos los cafés registrados. La brecha es un resultado: nunca entra a los modelos.

**Validación honesta.** Las celdas vecinas comparten alrededores, así que se parte por bloques de ciudad: {pt['bloques_prueba']}
de 108 bloques ({pt['celdas_prueba']} zonas) quedaron para prueba con semilla {pt['semilla']}. Modelo, parámetros, umbral y cortes
de la regla se eligieron con validación cruzada por bloques ({pt['pliegues']} pliegues) en entrenamiento; la prueba se usó una vez.

**Puntajes del mapa sin trampa.** Cada zona se puntúa con un modelo que no vio su bloque (predicciones fuera de bloque; AUC
{m['puntaje_oof']['auc_todas']:.3f} en las 3.275 zonas).

**Qué significa el puntaje.** Es la probabilidad de que una zona **con ese perfil tenga al menos un café**. No es la
probabilidad de que una tienda nueva de Cereza tenga éxito ni una calificación financiera.
""")

    with t[1]:
        st.markdown("##### Definición de las cuatro clases")
        ui.nota(f"<b>Propuesta {sup['version']} · {sup['estado']}.</b> Las definiciones las debe validar el equipo; "
                "están parametrizadas en <code>pipeline/build_artifacts.py</code> (SUPUESTOS).")
        d = sup["clasificacion"]["delta_cafes"]
        u = md["umbral"]
        defs = {
            "Saturada": f"Brecha ≤ −{d:g}: hay al menos {d:g} café más de los que el perfil sugiere (se evalúa primero).",
            "Sin demanda": f"Puntaje < {u:.2f} (el clasificador no la manda a estudiar) y no está saturada.",
            "Oportunidad": f"Puntaje ≥ {u:.2f} y brecha ≥ +{d:g}: perfil de demanda con al menos {d:g} café menos de lo esperado.",
            "En equilibrio": f"Puntaje ≥ {u:.2f} y brecha entre −{d:g} y +{d:g}.",
        }
        tasas = m["clases_tasa_cafe"]
        st.dataframe(pd.DataFrame([{"Clase": f"{CLASES[c]['simbolo']} {c}", "Regla": defs[c], "Zonas": m["clases"].get(c, 0),
                                    "% con café hoy": f"{tasas.get(c, 0) * 100:.0f} %"} for c in ORDEN_CLASES]), hide_index=True,
                     column_config={"Regla": st.column_config.TextColumn(width="large")})
        st.caption(f"El umbral {u:.2f} es el que minimiza el costo de errores (60 M por FN, 20 M por FP) en validación cruzada; "
                   f"la tolerancia de {d:g} café evita llamar oportunidad a diferencias pequeñas que el modelo de conteo no distingue.")
        s = m["sensibilidad_clases"]
        st.markdown("**Sensibilidad a la tolerancia** (número de zonas por clase)")
        st.dataframe(pd.DataFrame({f"Tolerancia {k} café": {c: v.get(c, 0) for c in ORDEN_CLASES} for k, v in s.items()}))

        st.markdown("**Pruebe otra tolerancia y otro umbral** (recalcula las clases en vivo; no cambia los artefactos)")
        a1, a2 = st.columns(2)
        d_v = a1.slider("Tolerancia de la brecha (cafés)", 0.25, 3.0, float(d), 0.25)
        u_v = a2.slider("Umbral de puntaje para ‘demanda’", 0.05, 0.6, float(u), 0.01)
        import numpy as np
        cl = np.select([z["brecha"] <= -d_v, z["puntaje"] < u_v, z["brecha"] >= d_v], ["Saturada", "Sin demanda", "Oportunidad"], "En equilibrio")
        vc = pd.Series(cl).value_counts()
        cc = st.columns(4)
        for col, c in zip(cc, ORDEN_CLASES):
            col.metric(ui.texto_clase(c), int(vc.get(c, 0)), delta=int(vc.get(c, 0)) - int(m["clases"].get(c, 0)), delta_color="off")
        st.caption("Delta frente a la propuesta v1. Una clasificación robusta no debería cambiar drásticamente con pequeños ajustes.")

        st.markdown("##### Incertidumbre y riesgo de cada zona")
        st.markdown(f"Para cada pliegue fuera de bloque se reentrenaron el clasificador y el modelo de conteo sobre "
                    f"{m['incertidumbre']['remuestreos_por_pliegue']} remuestreos de bloques. Cada zona tiene así 100 puntajes de "
                    "modelos que no vieron su bloque: de ahí salen el intervalo de 90 % del puntaje y la **estabilidad de la clase** "
                    "(porcentaje de remuestreos en que conserva su clase).")
        st.markdown("**Riesgo de la recomendación (propuesta v1, por puntos):** clase con estabilidad < 60 % (+2) o < 80 % (+1); "
                    "intervalo del puntaje > 25 puntos (+1); arriendo de referencia sobre el presupuesto (+2) o sobre el 80 % (+1); "
                    "3 o más cafés registrados (+1); dentro del radio de canibalización (+1); oportunidad sin cafés registrados, "
                    "por verificar (+1). **Bajo** 0–1 · **Medio** 2–3 · **Alto** 4 o más. Califica el riesgo de recomendar estudiar "
                    "la zona; no es una calificación crediticia.")
        st.markdown("##### Índice de sobremesa urbana (propuesta)")
        isu = m["isu"]
        st.markdown(isu["definicion"] + f" Estado: *{isu['estado']}*. No es entrada del modelo; describe zonas que invitan a quedarse.")
        st.dataframe(pd.DataFrame(isu["por_quintil"]).rename(columns={"quintil": "Quintil", "celdas": "Zonas", "tasa_cafe": "% con café",
                     "isu_min": "Índice mín.", "isu_max": "Índice máx."}), hide_index=True,
                     column_config={"% con café": st.column_config.NumberColumn(format="percent")})
        st.caption(f"Evidencia descriptiva: la proporción de zonas con café sube con el índice (AUC del índice solo {isu['auc_sola']:.2f}).")

        st.markdown("##### Filtro de arriendo")
        a, ac = sup["arriendo"], m["arriendo"]
        st.markdown(a["descripcion"])
        ui.kv([("Ancla", f"COP {a['ancla_millones_mes']:g} M/mes por {a['area_m2']} m² · {a['ancla_fuente']}"),
               ("Celdas usadas para el ancla", f"{ac['celdas_ancla']} (a {a['ancla_radio_m']} m de la tienda de Chapinero)"),
               ("Mediana del suelo en el ancla", f"COP {logic.fmt_m(ac['mediana_suelo_ancla'])} por m²"),
               ("Suelo máximo compatible con COP 12 M", f"COP {logic.fmt_m(ac['suelo_max_presupuesto'])} por m²"),
               ("Zonas dentro del presupuesto", f"{logic.fmt_m(ac['celdas_dentro_presupuesto'])} de 3.275")])
        st.warning("Con este supuesto el presupuesto de COP 12 M casi no restringe (solo excluye las zonas de suelo más caro). "
                   "La restricción real probablemente será la disponibilidad de locales y su arriendo efectivo, que el estudio de campo "
                   "debe medir. Si el equipo no valida el supuesto, el filtro debe tratarse como pendiente de calibración.", icon="🏷️")
        st.markdown("##### Proximidad y canibalización")
        st.markdown(sup["canibalizacion"]["descripcion"] + " El radio se ajusta en la barra lateral.")
        st.markdown("##### Criterio del ranking")
        st.markdown(sup["ranking"]["descripcion"])

    with t[2]:
        f = md["fechas_datos"]
        st.dataframe(pd.DataFrame([
            {"Fuente": "Overture Maps", "Uso": "Negocios por tipo a 300 m; cafés (target)", "Fecha": f["cafes"], "Licencia": "CDLA-Permissive 2.0"},
            {"Fuente": "Foursquare OS Places", "Uso": "Actividad comercial y oficinas históricas", "Fecha": f["foursquare"], "Licencia": "Apache 2.0"},
            {"Fuente": "OpenStreetMap", "Uso": "Universidades, colegios, oficinas, bancos, centros comerciales, clínicas, parques, paraderos SITP", "Fecha": f["osm"], "Licencia": "ODbL (atribución obligatoria)"},
            {"Fuente": "Catastro de Bogotá", "Uso": "Valor de referencia del m² de suelo", "Fecha": f["suelo"], "Licencia": "Datos abiertos"},
            {"Fuente": "TransMilenio", "Uso": "Validaciones por estación troncal", "Fecha": f["transmilenio"], "Licencia": "Datos abiertos"},
        ]), hide_index=True)
        st.markdown("**Cobertura:** 3.275 celdas H3 de resolución 9 (~0,1 km²) del área urbana; todas con manzanas catastrales y valor "
                    "del suelo. **Unidad:** cada celda cuenta lo que hay en ella y en sus seis vecinas (~300 m).")
        st.markdown("**Columnas excluidas de los modelos:** cafés por nombre y nombres de cafés (fuga: solo existen donde hay cafés), "
                    "cafés históricos de Foursquare (misma oferta con otra fuente), restaurantes y bares (oferta, no demanda), "
                    "identificadores y coordenadas (el modelo memorizaría ubicaciones).")
        st.markdown("**Publicación:** el repositorio no contiene el archivo original del curso; solo la tabla de celdas con resultados y "
                    "las variables de entrada necesarias para la predicción, sin nombres de negocios.")

    with t[3]:
        for titulo, txt in [
            ("No garantiza rentabilidad", "El target es ‘hay café hoy’; un café puede existir y perder dinero. El estudio de campo es el filtro que verifica."),
            ("Negocios no registrados", "Un 0 en cafés puede ser un café que Overture no registró: una ‘oportunidad’ puede tener competencia real."),
            ("Uso del suelo", "No todas las zonas admiten locales comerciales; la tabla no trae el POT."),
            ("Competencia registrada ≠ real", "No distingue especialidad, cadena o panadería en el conteo usado por los modelos."),
            ("Suelo ≠ arriendo", "El arriendo de referencia es un supuesto proporcional al valor del suelo, anclado en un solo dato."),
            ("Proximidad ≠ canibalización", "Estar cerca no demuestra que se quiten clientes; depende del público y del formato."),
            ("Cambios en el tiempo", "Foursquare es mayormente de 2011–2016 y TransMilenio de 2025; el metro y nuevas estaciones cambiarán los patrones."),
            ("Asociación, no causa", "La importancia de variables y SHAP describen qué usa el modelo, no qué pasaría si se cambiara una variable."),
            ("Incertidumbre", "Con 22 bloques de prueba los intervalos son anchos; por eso no se afirma que el modelo supere a la regla."),
        ]:
            st.markdown(f"**{titulo}.** {txt}")

    with t[4]:
        if config.RUTA_FICHA.exists():
            st.markdown(config.RUTA_FICHA.read_text(encoding="utf-8"))
        else:
            ui.pendiente("Ficha del modelo no encontrada", "Agregue docs/ficha_modelo.md.")

    with t[5]:
        st.markdown("""
- **© colaboradores de OpenStreetMap** — datos bajo licencia ODbL 1.0 (openstreetmap.org/copyright).
- **Overture Maps Foundation** — Places, versión de septiembre de 2026, licencia CDLA-Permissive 2.0.
- **Foursquare Open Source Places** — licencia Apache 2.0.
- **Unidad Administrativa Especial de Catastro Distrital** — valor de referencia de terreno 2026, Datos Abiertos Bogotá.
- **TransMilenio S.A.** — validaciones del sistema troncal, septiembre de 2025, Datos Abiertos Bogotá.
- **Mapa base** © CARTO, con datos © colaboradores de OpenStreetMap.
- **Software:** Streamlit, pydeck, H3 (Uber), scikit-learn (Pedregosa et al., 2011), SHAP.

Cereza Café es una marca ficticia del curso Minería de Datos (ADMI 2559), Universidad de los Andes. Las cifras del mercado y los
datos de la ciudad son reales. Arriendos de referencia: Fincaraíz (2026), consulta citada en el brief del curso.
""")
        with st.expander("Registro de la generación de artefactos"):
            st.code("\n".join(m.get("log", [])), language=None)
            st.caption(f"Generado: {m['generado']} · huella del archivo de datos (MD5): {m['fuente_md5']}")
