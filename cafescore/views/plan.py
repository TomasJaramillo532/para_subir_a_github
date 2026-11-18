"""Módulo complementario — Plan de estudio de campo (fundadora y analista de crédito)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from .. import data, logic, maps, sim, ui
from .explorador import _base_mapa
from .resumen import ranking_oficial


@st.cache_data(show_spinner=False)
def boot_matrix(n_bloques: int):
    return sim.matriz_bootstrap(n_bloques)


def render():
    md, m, z = data.metadata(), data.metricas(), data.zonas()
    presupuesto, radio = st.session_state.presupuesto, st.session_state.radio
    ui.encabezado("Plan de estudio de campo", "¿Cuántas zonas estudiar y cuánto presupuestar?",
                  "Arme la lista de zonas para visitar y vea el costo, la probabilidad de encontrar dos zonas aptas, "
                  "el riesgo y la distancia entre las futuras tiendas.")

    _, r = ranking_oficial(z, md, presupuesto, radio)
    if "plan" not in st.session_state or not st.session_state["plan"]:
        st.session_state["plan"] = r["h3"].tolist()[:4]
    cand = z[(z["clase"] == "Oportunidad") | z["h3"].isin(st.session_state["plan"])].copy()
    cand["etq"] = [f"{logic.referencia(f)} · {f['h3'][-6:]}" for _, f in cand.iterrows()]
    etq = dict(zip(cand["h3"], cand["etq"]))
    plan = st.multiselect("Zonas del plan (máximo 8)", list(etq), default=[h for h in st.session_state["plan"] if h in etq],
                          format_func=etq.get, max_selections=8,
                          help="Por defecto, las primeras zonas del ranking oficial. Puede agregar cualquier zona de oportunidad.")
    st.session_state["plan"] = plan
    if not plan:
        ui.pendiente("El plan está vacío", "Agregue zonas desde la lista o use el botón del módulo Ranking.")
        return
    sel = z.set_index("h3").loc[plan].reset_index()

    sm = m["simulador"]
    prec, (plo, phi) = sim.precision_bootstrap(sm, md["umbral"], boot_matrix(sm["bloques"]))
    k = len(plan)
    p2, p2lo, p2hi = (logic.binom_al_menos(2, k, x) for x in (prec, plo, phi))
    rec = logic.estudios_necesarios(prec)
    c = st.columns(4)
    c[0].metric("Zonas a estudiar", k, border=True)
    c[1].metric("Costo de los estudios", logic.fmt_cop(k * md["costos"]["estudio"]), border=True, help="COP 20 M por zona (brief).")
    c[2].metric("Prob. de hallar ≥ 2 zonas aptas", f"{p2 * 100:.0f} %", border=True,
                delta=f"rango {p2lo * 100:.0f}–{p2hi * 100:.0f} %", delta_color="off", delta_arrow="off",
                help=f"Binomial con la precisión del modelo en prueba ({prec * 100:.1f} %, IC 95 % {plo * 100:.1f}–{phi * 100:.1f} %).")
    c[3].metric("Estudios sugeridos", rec or "—", border=True,
                help="Mínimo de estudios para tener 80 % de probabilidad de hallar 2 zonas aptas, con la precisión del modelo en prueba.")
    ui.nota(f"<b>Cómo leerlo.</b> En las 732 zonas de prueba, {prec * 100:.0f} de cada 100 zonas que el modelo mandó a estudiar tenían café "
            "(el proxy de ‘zona apta’ del caso). Se supone que cada estudio es independiente y tiene esa tasa de acierto. "
            "‘Apta’ no significa rentable: el estudio de campo es el que decide.")

    st.markdown("##### Zonas del plan")
    filas = []
    for _, f in sel.iterrows():
        nivel, pts, _ = logic.riesgo(f, presupuesto, radio)
        esc = logic.escenario(f["arriendo_ref_millones"])
        filas.append({"Zona": logic.referencia(f), "Clase": ui.texto_clase(f["clase"]), "Puntaje": f["puntaje"],
                      "Riesgo": f"{nivel} ({pts})", "Sobremesa": round(f["isu"]),
                      "Arriendo ref. (M/mes)": round(f["arriendo_ref_millones"], 1),
                      "Margen tras arriendo (M/mes)": round(esc["margen_neto"], 1),
                      "Meses para recuperar 250 M": round(esc["meses_recuperacion"]) if esc["meses_recuperacion"] else None,
                      "Tienda más cercana": f"{f['tienda_cercana']} · {logic.fmt_m(f['dist_min_m'])} m", "H3": f["h3"]})
    t = pd.DataFrame(filas)
    st.dataframe(t, hide_index=True, column_config={
        "Puntaje": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
        "Margen tras arriendo (M/mes)": st.column_config.NumberColumn(help="Escenario: margen de 15 M/mes (brief) menos el arriendo de referencia."),
        "Meses para recuperar 250 M": st.column_config.NumberColumn(help="Escenario: adecuación de 250 M (brief) / margen tras arriendo. No es una proyección."),
    })
    st.caption("Margen y meses de recuperación son un escenario con los supuestos del brief (margen de COP 15 M antes de arriendo y "
               "adecuación de COP 250 M) y el arriendo de referencia. No son una proyección financiera de la tienda.")

    a, b = st.columns([1.3, 1], gap="large")
    with a:
        d, _ = maps.colorear(_base_mapa(), "Clasificación de zonas", presupuesto)
        d["color"] = [[c[0], c[1], c[2], 70] for c in d["color"]]
        st.pydeck_chart(maps.deck(d, md["tiendas"], extra=sel, zoom=10.6), height=420, key="mapa_plan")
        st.caption("Zonas del plan resaltadas en cereza; ★ tiendas actuales.")
    with b:
        st.markdown("##### Distancia entre zonas del plan")
        pares = logic.distancias_entre(sel)
        cerca = [(x, y, d_) for x, y, d_ in pares if d_ < radio]
        if cerca:
            for x, y, d_ in cerca:
                st.warning(f"{etq.get(x, x)} y {etq.get(y, y)} están a {logic.fmt_m(d_)} m: si ambas se abren, "
                           "podrían competir entre sí.", icon="⚠️")
        elif pares:
            st.success(f"Todas las zonas del plan están a más de {logic.fmt_m(radio)} m entre sí "
                       f"(mínimo {logic.fmt_m(min(p[2] for p in pares))} m).", icon="✅")
        sectores = sel["tm_estacion"].nunique()
        st.markdown(f"**Diversificación:** {sectores} sector(es) de TransMilenio distintos y "
                    f"{sel['tienda_cercana'].nunique()} tienda(s) actual(es) como referencia de cercanía.")
        st.markdown("##### Exposición para la analista de crédito")
        ui.kv([("Estudios de campo", logic.fmt_cop(k * md["costos"]["estudio"])),
               ("Adecuación de dos tiendas (brief)", logic.fmt_cop(500)),
               ("Arriendo anual de referencia (dos zonas más baratas)",
                logic.fmt_cop(12 * sel.nsmallest(min(2, k), "arriendo_ref_millones")["arriendo_ref_millones"].sum(), 1)),
               ("Riesgo medio del plan", f"{np.mean([logic.riesgo(f, presupuesto, radio)[1] for _, f in sel.iterrows()]):.1f} puntos")])
    st.download_button("Descargar plan (CSV)", t.to_csv(index=False).encode("utf-8-sig"), "cafescore_plan_estudio.csv", "text/csv")
