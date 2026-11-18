"""Módulo 2 — Explorador geográfico."""
from __future__ import annotations

import streamlit as st

from .. import data, maps, ui
from ..config import ORDEN_CLASES
from ..geo import localizar
from . import zona


@st.cache_data(show_spinner=False)
def _base_mapa():
    return maps.preparar_tooltip(data.zonas())


def render():
    md, z = data.metadata(), data.zonas()
    presupuesto, radio = st.session_state.presupuesto, st.session_state.radio
    ui.encabezado("Módulo 2 · Explorador geográfico", "Mapa de oportunidades de Bogotá",
                  "3.275 zonas hexagonales H3 (~0,1 km² cada una). Haga clic en una zona o consulte unas coordenadas.")

    c1, c2 = st.columns([1.3, 2])
    capa = c1.selectbox("Capa del mapa", list(maps.CAPAS), key="capa_exp")
    visibles = c2.pills("Mostrar clases", ORDEN_CLASES, selection_mode="multi", default=ORDEN_CLASES, key="clases_exp",
                        format_func=ui.texto_clase,
                        help="Las clases no seleccionadas se atenúan en el mapa.")

    col_mapa, col_panel = st.columns([1.85, 1.15], gap="large")
    with col_mapa:
        d, ley = maps.colorear(_base_mapa(), capa, presupuesto)
        if visibles is not None and set(visibles) != set(ORDEN_CLASES):
            ocultas = ~d["clase"].isin(visibles or [])
            d.loc[ocultas, "color"] = [[c[0], c[1], c[2], 25] for c in d.loc[ocultas, "color"]]
        sel_actual = st.session_state.get("h3_sel")
        vista = maps.vista_en(sel_actual) if (sel_actual and st.session_state.get("_zoom_sel")) else None
        ev = st.pydeck_chart(maps.deck(d, md["tiendas"], sel_actual, vista=vista), on_select="rerun",
                             selection_mode="single-object", key="mapa_exp", height=600)
        objs = (ev.selection.objects.get("zonas") if ev and ev.selection else None) or []
        if objs:
            h = objs[0].get("h3")
            if h and h != st.session_state.get("_ultimo_click"):
                st.session_state["_ultimo_click"] = h
                st.session_state.update(h3_sel=h, _msg_coord=None, _zoom_sel=False)
                st.rerun()
        if ley["tipo"] == "clases":
            ui.leyenda_clases(z["clase"].value_counts().to_dict())
        elif ley["tipo"] == "categorias":
            st.markdown(" · ".join(f"<span style='color:rgb({c[0]},{c[1]},{c[2]})'>■</span> {k}"
                                   for k, c in ley["items"].items()), unsafe_allow_html=True)
        else:
            ui.leyenda_continua(ley["titulo"], ley["colores"], ley["etiquetas"], ley.get("nota", ""))
        st.caption("ℹ️ " + maps.EXPLICACION[capa] + " ★ Tiendas actuales de Cereza.")

    with col_panel:
        estaciones = sorted(z["tm_estacion"].dropna().unique())
        est = st.selectbox("Ir a una zona por estación de TransMilenio", ["—"] + estaciones, key="est_exp",
                           help="Selecciona la zona más cercana a la estación troncal elegida.")
        if est != "—" and est != st.session_state.get("_ultima_est"):
            st.session_state["_ultima_est"] = est
            fila = z[z["tm_estacion"] == est].sort_values("dist_tm_m").iloc[0]
            st.session_state.update(h3_sel=fila["h3"], _zoom_sel=True, _msg_coord=None)
            st.rerun()
        with st.form("consulta_coord", border=True):
            st.markdown("**Consultar una ubicación**")
            a, b = st.columns(2)
            lat = a.number_input("Latitud", value=4.6486, format="%.5f", step=0.001)
            lon = b.number_input("Longitud", value=-74.0628, format="%.5f", step=0.001)
            if st.form_submit_button("Buscar zona", type="primary", width="stretch"):
                r = localizar(lat, lon, set(z["h3"]))
                if r.estado == "ok":
                    st.session_state.update(h3_sel=r.h3, _msg_coord=None, _zoom_sel=True)
                    st.rerun()
                else:
                    st.session_state["_msg_coord"] = r.mensaje
        if st.session_state.get("_msg_coord"):
            st.error(st.session_state["_msg_coord"], icon="📍")

        sel = st.session_state.get("h3_sel")
        if sel and sel in set(z["h3"]):
            with st.container(border=True):
                zona.panel(z.loc[z["h3"] == sel].iloc[0], md, presupuesto, radio)
                if st.button("Limpiar selección", width="stretch"):
                    st.session_state.update(h3_sel=None, _zoom_sel=False)
                    st.rerun()
        else:
            ui.pendiente("Ninguna zona seleccionada",
                         "Haga clic en un hexágono del mapa o escriba unas coordenadas para ver su puntaje, clase, "
                         "razones, costo y distancia a las tiendas actuales.")
