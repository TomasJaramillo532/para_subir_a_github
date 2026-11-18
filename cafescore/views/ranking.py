"""Módulo 3 — Ranking y análisis de oportunidades."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import charts, data, logic, ui
from ..config import CLASES, ORDEN_CLASES
from . import zona


def tabla_ranking(r: pd.DataFrame, md: dict, presupuesto: float, radio: float) -> pd.DataFrame:
    et = md["etiquetas"]
    return pd.DataFrame({
        "Pos.": r["posicion"],
        "Zona": [logic.referencia(f) for _, f in r.iterrows()],
        "Clase": r["clase"].map(lambda c: f"{CLASES[c]['simbolo']} {c}"),
        "Puntaje": r["puntaje"],
        "Cafés hoy": r["n_cafes"],
        "Esperados": r["cafes_esperados"].round(1),
        "Brecha": r["brecha"].round(1),
        "Justificación": [logic.justificacion(f, et) for _, f in r.iterrows()],
        "Suelo (COP/m²)": r["valor_suelo_m2"],
        "Arriendo ref. (M/mes)": r["arriendo_ref_millones"].round(1),
        "Presupuesto": [logic.estado_presupuesto(a, presupuesto) for a in r["arriendo_ref_millones"]],
        "Dist. mín. (m)": r["dist_min_m"].round(0),
        "Tienda cercana": r["tienda_cercana"],
        "Riesgo": [logic.riesgo(f, presupuesto, radio)[0] for _, f in r.iterrows()],
        "Estabilidad": r["estabilidad_clase"],
        "Sobremesa": r["isu"].round(0),
        "Alertas": [" · ".join(logic.alertas(f, presupuesto, radio)) or "—" for _, f in r.iterrows()],
        "H3": r["h3"],
    })


COLCFG = {
    "Puntaje": st.column_config.ProgressColumn("Puntaje", format="percent", min_value=0, max_value=1,
                                               help="Probabilidad fuera de bloque de que una zona con este perfil tenga café"),
    "Suelo (COP/m²)": st.column_config.NumberColumn(format="localized"),
    "Dist. mín. (m)": st.column_config.NumberColumn(format="localized"),
    "Justificación": st.column_config.TextColumn(width="large"),
    "Alertas": st.column_config.TextColumn(width="large"),
    "Estabilidad": st.column_config.NumberColumn(format="percent", help="% de 100 remuestreos en que la zona conserva su clase"),
    "Sobremesa": st.column_config.NumberColumn(help="Índice de sobremesa urbana 0–100 (propuesta)"),
    "Riesgo": st.column_config.TextColumn(help="Riesgo de recomendar estudiar la zona (Bajo/Medio/Alto), ver Metodología"),
}


def render():
    md, z = data.metadata(), data.zonas()
    presupuesto, radio = st.session_state.presupuesto, st.session_state.radio
    sep_def = md["supuestos"]["ranking"]["separacion_min_m"]
    ui.encabezado("Módulo 3 · Ranking", "Dónde empezar el estudio de campo",
                  "Convierte los puntajes en una lista corta de zonas para estudiar, con costo, proximidad y alertas.")
    st.caption(f"Presupuesto de arriendo: **COP {presupuesto:g} M/mes** · radio de canibalización: **{logic.fmt_m(radio)} m** "
               "(se ajustan en la barra lateral).")

    with st.container(border=True):
        f1, f2, f3 = st.columns(3)
        clases = f1.multiselect("Clasificación", ORDEN_CLASES, default=["Oportunidad"])
        pmin, pmax = f2.slider("Rango de puntaje (%)", 0, 100, (0, 100), step=5)
        dmin, dmax = f3.slider("Distancia a la tienda más cercana (km)", 0.0, 15.0, (0.0, 15.0), step=0.5)
        g1, g2, g3, g4 = st.columns(4)
        excl = g1.toggle("Excluir radio de canibalización", value=True)
        solo_pres = g2.toggle("Solo dentro del presupuesto", value=True)
        separar = g3.toggle(f"Separar zonas (≥ {sep_def} m)", value=True,
                            help="Evita que el ranking se llene de celdas pegadas del mismo sector.")
        max_c = g4.number_input("Máx. cafés en la celda", 0, 30, 30, help="Para evitar calles ya llenas de cafés.")
        h1, h2 = st.columns(2)
        riesgo_max = h1.segmented_control("Riesgo máximo aceptado", ["Bajo", "Medio", "Alto"], default="Alto",
                                          help="Calificación por puntos: estabilidad, incertidumbre, arriendo, competencia, cercanía.")
        est_min = h2.slider("Estabilidad mínima de la clase (%)", 0, 100, 0, step=10)

    f = logic.filtrar(z, presupuesto, clases, (pmin / 100, pmax / 100),
                      (max(dmin * 1000, radio if excl else 0), dmax * 1000), max_c, solo_pres)
    orden_r = {"Bajo": 0, "Medio": 1, "Alto": 2}
    if riesgo_max and riesgo_max != "Alto":
        f = f[[orden_r[logic.riesgo(x, presupuesto, radio)[0]] <= orden_r[riesgo_max] for _, x in f.iterrows()]]
    f = f[f["estabilidad_clase"] >= est_min / 100]
    r = logic.rankear(f, n=10, separacion_m=sep_def if separar else 0)

    st.markdown(f"#### Top {len(r)} de {len(f)} zonas que cumplen los filtros")
    if r.empty:
        st.warning("Ninguna zona cumple los filtros. Amplíe el rango de puntaje o de distancia, o incluya otras clases.")
        return
    t = tabla_ranking(r, md, presupuesto, radio)
    ev = st.dataframe(t, hide_index=True, column_config=COLCFG, on_select="rerun", selection_mode="single-row",
                      key="tabla_rank", height=min(42 * len(t) + 40, 460))
    if st.button("Llevar estas zonas al plan de estudio de campo", icon=":material/assignment_add:"):
        st.session_state["plan"] = r["h3"].tolist()[:6]
        st.toast("Plan actualizado: abra «Plan de estudio» en el menú.", icon="✅")
    c1, c2 = st.columns([3, 1])
    c1.caption("Orden: brecha (cafés que faltan frente al perfil) y luego puntaje. Seleccione una fila para ver el detalle. "
               "Arriendo de referencia = supuesto calibrado con el promedio de Chapinero Central; no es un arriendo observado.")
    c2.download_button("Descargar ranking (CSV)", t.to_csv(index=False).encode("utf-8-sig"),
                       "cafescore_ranking.csv", "text/csv", width="stretch")
    filas = ev.selection.rows if ev and ev.selection else []
    if filas:
        with st.container(border=True):
            zona.panel(r.iloc[filas[0]], md, presupuesto, radio)

    st.divider()
    st.markdown("#### Comparador de zonas")
    opciones = {f"{int(p)}. {logic.referencia(fl)}": fl["h3"] for p, (_, fl) in zip(r["posicion"], r.iterrows())}
    elegidas = st.multiselect("Elija 2 o 3 zonas del ranking", list(opciones), default=list(opciones)[:2], max_selections=3)
    if len(elegidas) >= 2:
        sub = r.set_index("h3").loc[[opciones[e] for e in elegidas]].reset_index()
        sub["zona"] = elegidas
        cols = st.columns(len(sub))
        for col, (_, fl) in zip(cols, sub.iterrows()):
            with col.container(border=True):
                st.markdown(f"**{fl['zona']}**")
                ui.badge_clase(fl["clase"])
                ui.kv([("Puntaje", f"{fl['puntaje'] * 100:.0f} %"), ("Cafés hoy / esperados", f"{int(fl['n_cafes'])} / {fl['cafes_esperados']:.1f}"),
                       ("Brecha", f"{fl['brecha']:+.1f}"), ("Arriendo ref.", logic.fmt_cop(fl['arriendo_ref_millones'], 1) + "/mes"),
                       ("Tienda más cercana", f"{fl['tienda_cercana']} · {logic.fmt_m(fl['dist_min_m'])} m"),
                       ("Tipo de zona", fl["segmento"])])
                st.caption(logic.justificacion(fl, md["etiquetas"]))
        a, b = st.columns(2)
        a.altair_chart(charts.comparador(sub, "brecha", "Brecha (cafés que faltan)"), width="stretch")
        b.altair_chart(charts.comparador(sub, "arriendo_ref_millones", "Arriendo de referencia (COP M/mes)"), width="stretch")
    else:
        st.caption("Seleccione al menos dos zonas para compararlas.")

    st.divider()
    st.markdown("#### Qué significa esta lista")
    n_op = int((z["clase"] == "Oportunidad").sum())
    k1, k2, k3 = st.columns(3)
    k1.metric("1 · Zonas prometedoras para estudiar", f"{n_op}", help="Clase Oportunidad en todo el mapa.")
    k2.metric("2 · Superan los filtros adicionales", f"{len(f)}", help="Presupuesto, distancia y demás filtros actuales.")
    k3.metric("3 · Locales validados para abrir", "0", help="Solo el estudio de campo valida un local.")
    ui.nota("CaféScore indica <b>dónde empezar el estudio de campo</b>. Una zona del ranking no es un local validado: "
            "falta verificar locales disponibles y su arriendo real, el uso del suelo permitido, el flujo peatonal y la "
            "competencia no registrada. Ninguna ubicación garantiza rentabilidad.")
