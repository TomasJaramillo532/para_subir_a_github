"""Evaluar una zona con datos propios (formulario de la plantilla, adaptado). Usa la zona fija: validar → evaluar."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import core

from .. import data, logic, ui

GRUPOS = {
    "Comercio y servicios a 300 m": ["ov_comercio_300m", "ov_servicios_empresas_300m", "ov_belleza_estilo_300m",
                                     "ov_entretenimiento_300m", "ov_salud_300m", "ov_educacion_300m", "ov_hoteles_300m",
                                     "ov_deporte_300m", "fsq_negocios_hist_300m", "fsq_oficinas_hist_300m"],
    "Generadores de demanda a 300 m": ["osm_oficinas_osm_300m", "osm_universidades_300m", "osm_colegios_300m",
                                       "osm_bancos_300m", "osm_centros_comerciales_300m", "osm_parques_300m",
                                       "osm_hospitales_clinicas_300m"],
    "Movilidad": ["dist_tm_m", "tm_flujo_mes", "tm_a_500m", "osm_paraderos_sitp_300m"],
    "Suelo y manzanas": ["valor_suelo_m2", "n_manzanas"],
}


def _construidas(v: dict) -> dict:
    """Variables construidas del cuaderno, calculadas igual que en el entrenamiento."""
    import numpy as np
    v = dict(v)
    v["mezcla_oficina_uni"] = v["osm_universidades_300m"] * v["osm_oficinas_osm_300m"]
    v["densidad_comercial_total"] = v["ov_comercio_300m"] + v["ov_servicios_empresas_300m"] + v["ov_entretenimiento_300m"]
    v["accesibilidad_transporte"] = v["tm_flujo_mes"] / (v["dist_tm_m"] + 1)
    tipos = [k for k in v if k.startswith("ov_")]
    tot = sum(v[k] for k in tipos)
    v["diversidad_usos"] = float(-sum((v[k] / tot) * np.log(v[k] / tot) for k in tipos if v[k] > 0)) if tot > 0 else 0.0
    return v


def render():
    meta, modelo = data.modelo()
    z = data.zonas()
    ui.encabezado("Evidencia · Zona fija de la plantilla", "Evaluar una zona con datos nuevos",
                  "Para un local que conoce el equipo o un escenario (por ejemplo, una estación nueva): escriba los datos del "
                  "entorno y el modelo exportado calcula la probabilidad, la recomendación y sus razones.")
    ui.nota("Parte de una zona existente y cambie lo que sepa del sitio. Las variables construidas (mezcla de oficinas y "
            "universidades, densidad comercial, accesibilidad y diversidad de usos) se recalculan solas, igual que en el cuaderno. "
            "Esto <b>no</b> dice qué pasaría si la zona cambiara: muestra cómo puntuaría el modelo una zona con ese perfil.")

    ests = sorted(z["tm_estacion"].dropna().unique())
    base_est = st.selectbox("Partir de la zona más cercana a la estación", ests,
                            index=ests.index("Calle 76") if "Calle 76" in ests else 0)
    base = z[z["tm_estacion"] == base_est].sort_values("dist_tm_m").iloc[0]
    cols_meta = {c["nombre"]: c for c in meta["columnas"]}
    valores = {}
    with st.form("evaluar_zona"):
        for grupo, cols in GRUPOS.items():
            st.markdown(f"**{grupo}**")
            cc = st.columns(4)
            for i, c in enumerate(cols):
                cm = cols_meta[c]
                valores[c] = cc[i % 4].number_input(core.etiqueta(meta, c), min_value=0.0, value=float(base[c]),
                                                    help=f"Rango visto al entrenar: {cm['minimo']:g} a {cm['maximo']:g}",
                                                    key=f"ev_{c}_{base['h3']}")
        enviado = st.form_submit_button("Evaluar con el modelo", type="primary")
    if not enviado:
        st.caption(f"Valores iniciales: zona `{base['h3']}` ({logic.referencia(base)}).")
        return
    fila = _construidas(valores)
    datos, errores, avisos = core.validar(pd.DataFrame([fila]), meta)
    for e in errores:
        st.error(e, icon="⛔")
    for a in avisos:
        st.warning(a, icon="⚠️")
    if errores:
        return
    r = core.evaluar(modelo, meta, datos)[0]
    c1, c2 = st.columns(2)
    c1.metric(f"Probabilidad de {meta['evento']}", f"{r['probabilidad']:.0%}", border=True)
    c2.metric("Recomendación (umbral 0,25)", r["decision"], border=True)
    st.markdown("**Razones principales**")
    if r["razones"]:
        st.markdown("\n".join(f"- {core.texto_razon(x, meta)}" for x in r["razones"]))
    else:
        st.caption("Con estos valores ninguna variable mueve la probabilidad frente a una zona típica.")
    st.caption("Las razones muestran de qué depende la predicción del modelo, no qué pasaría si algo cambiara. "
               "La probabilidad viene del modelo exportado (entrenado con los bloques de entrenamiento).")
