"""Módulo 1 — Resumen ejecutivo (pantalla principal)."""
from __future__ import annotations

import html

import streamlit as st

from .. import data, logic, maps, nav, reports, ui
from .explorador import _base_mapa
from .ranking import COLCFG, tabla_ranking


def ranking_oficial(z, md, presupuesto, radio):
    f = logic.filtrar(z, presupuesto, ["Oportunidad"], (0, 1), (radio, 1e9), None, True)
    return f, logic.rankear(f, 10, md["supuestos"]["ranking"]["separacion_min_m"])


def render():
    md, m, z = data.metadata(), data.metricas(), data.zonas()
    presupuesto, radio = st.session_state.presupuesto, st.session_state.radio
    sel = m["seleccionado"]
    fs = data.fila_metodo(m, sel)

    ui.encabezado("Cereza Café · Expansión 2027", "¿Dónde buscar local para las dos próximas tiendas?",
                  "Mapa de oportunidades construido con datos abiertos de Bogotá: perfil de demanda, competencia, costo "
                  "del suelo y proximidad a las tiendas actuales.")
    b = st.container(horizontal=True, gap="small")
    with b:
        st.badge(f"Modelo disponible · {sel}", icon=":material/check_circle:", color="green")
        st.badge("Cafés: Overture, sept. 2026 · Suelo: Catastro 2026 · TM: sept. 2025", icon=":material/event:", color="gray")
        st.badge("Supuestos de despliegue v1: pendientes de validación del equipo", icon=":material/rule:", color="orange")

    f, r = ranking_oficial(z, md, presupuesto, radio)
    n_op = int((z["clase"] == "Oportunidad").sum())

    rol = st.segmented_control("Vista por rol", ["Fundadora", "Analista de crédito", "Jefe de operaciones"],
                               default="Fundadora", key="rol", help="Muestra qué mirar primero según quién usa la herramienta.")
    guia = {
        "Fundadora": ("Dónde buscar local, por qué y con qué presupuesto.",
                      [("ranking", "Ranking de las 10 zonas para estudiar", ":material/format_list_numbered:"),
                       ("plan", "Plan de estudio y presupuesto", ":material/assignment:"),
                       ("explorador", "Explorar una zona en el mapa", ":material/map:")]),
        "Analista de crédito": ("Riesgo, incertidumbre y justificación económica de cada recomendación.",
                                [("desempeno", "Evidencia frente a la regla", ":material/query_stats:"),
                                 ("plan", "Exposición del plan", ":material/account_balance:"),
                                 ("metodologia", "Supuestos y ficha del modelo", ":material/menu_book:")]),
        "Jefe de operaciones": ("Cercanía a las tiendas actuales y entre las nuevas tiendas.",
                                [("explorador", "Distancias a las tiendas", ":material/map:"),
                                 ("plan", "Distancia entre zonas del plan", ":material/route:"),
                                 ("ranking", "Ranking por distancia", ":material/tune:")]),
    }.get(rol or "Fundadora")
    with st.container(border=True):
        st.markdown(f"**{rol or 'Fundadora'}:** {guia[0]}")
        cols = st.columns(3)
        for col, (clave, txt, ico) in zip(cols, guia[1]):
            with col:
                nav.enlace(clave, txt, ico)
    k = st.columns(4)
    k[0].metric("Zonas analizadas", logic.fmt_m(len(z)), border=True)
    k[1].metric("Oportunidades", n_op, border=True, help="Perfil de demanda con al menos 1 café menos de lo esperado.")
    k[2].metric("Candidatas tras filtros", len(f), border=True,
                help=f"Oportunidad, arriendo de referencia ≤ COP {presupuesto:g} M y a más de {logic.fmt_m(radio)} m de una tienda.")
    val = m["valor"]
    k[3].metric("Valor frente a la regla", logic.fmt_cop(val["ahorro_vs_regla"], 1), border=True,
                delta="no concluyente: IC incluye 0", delta_color="off", delta_arrow="off",
                help="Ahorro esperado en estudios de campo para hallar 2 zonas aptas, frente a la regla simple.")
    if len(r):
        b0 = r.iloc[0]
        ui.nota(f"<b>★ Mejor alternativa identificada:</b> zona {html.escape(logic.referencia(b0))} "
                f"(<code>{b0['h3']}</code>) · {ui.texto_clase(b0['clase'])} · {int(b0['n_cafes'])} café(s) hoy frente a "
                f"{logic.fmt_num(b0['cafes_esperados'], 1)} esperados · arriendo de referencia "
                f"{logic.fmt_cop(b0['arriendo_ref_millones'], 1)}/mes · {logic.fmt_m(b0['dist_min_m'])} m de {b0['tienda_cercana']}.")

    c1, c2 = st.columns([1.5, 1], gap="large")
    with c1:
        st.markdown("##### Vista general de la ciudad")
        vista = st.segmented_control("Mostrar en el mapa", ["Clasificación de zonas", "Índice de sobremesa urbana"],
                                     default="Clasificación de zonas", key="capa_resumen") or "Clasificación de zonas"
        capa = "Clasificación de zonas" if vista.startswith("Clas") else "Índice de sobremesa urbana (propuesta)"
        d, ley = maps.colorear(_base_mapa(), capa, presupuesto)
        st.pydeck_chart(maps.deck(d, md["tiendas"], zoom=10.05), height=460, key="mapa_resumen")
        if ley["tipo"] == "clases":
            ui.leyenda_clases(z["clase"].value_counts().to_dict())
        else:
            ui.leyenda_continua(ley["titulo"], ley["colores"], ley["etiquetas"],
                                "Oficinas, universidades y espacios de permanencia a 300 m. Más alto = la zona invita a quedarse.")
        st.caption("Para consultar una zona o unas coordenadas, abra **Explorador geográfico** en el menú.")

    with c2:
        st.markdown("##### Recomendación ejecutiva")
        lo, hi = fs["dif_vs_regla_ic95"]
        sectores = []
        for _, fl in r.iterrows():
            s = fl.get("tm_estacion")
            if s not in sectores:
                sectores.append(s)
        st.markdown(
            f"- **Dónde mirar primero:** los alrededores de {', '.join('TM ' + s for s in sectores[:3])}. Son zonas con perfil de "
            "demanda alto (comercio, entretenimiento, oficinas) y menos cafés de los que ese perfil sugiere.\n"
            f"- **Presupuesto:** con el supuesto de arriendo actual, {len(f)} de {n_op} zonas de oportunidad caben en COP "
            f"{presupuesto:g} M/mes. El arriendo real debe confirmarse local por local.\n"
            f"- **Operaciones:** el ranking excluye zonas a menos de {logic.fmt_m(radio)} m de las tiendas actuales.\n"
            f"- **Evidencia:** el modelo comete errores {logic.fmt_cop(-fs['dif_vs_regla'])} más baratos que la regla simple en "
            f"zonas de prueba, pero el intervalo ({logic.fmt_num(lo, signo=True)} a {logic.fmt_num(hi, signo=True)} M) incluye el cero. **La regla simple sería suficiente "
            "para preseleccionar**; el mapa agrega el orden de prioridad, las razones y la detección de zonas saturadas.\n"
            + f"- **Sobremesa urbana:** las cinco primeras zonas promedian {r.head(5)['isu'].mean():.0f}/100 frente a "
              f"{z['isu'].mean():.0f} en la ciudad: más oficinas, universidades y lugares donde la gente se queda (índice propuesto).\n"
            + "- **Pendiente:** validación con las aperturas abril–septiembre 2026 (archivo aún no entregado)."
        )
        ui.nota("Use esta lista para decidir <b>dónde hacer estudios de campo</b> (COP 20 M c/u), no para firmar un local.")
        st.download_button("Descargar memo para la fundadora", reports.memo(r, m, md, presupuesto, radio, n_op, len(f),
                           float(z["isu"].mean())).encode("utf-8"), "cafescore_memo.html", "text/html",
                           type="primary", width="stretch", icon=":material/description:",
                           help="Una página imprimible: abrir en el navegador y guardar como PDF.")

    st.markdown("##### Las cinco primeras zonas para estudiar")
    with st.expander("¿Cómo usar CaféScore en 2 minutos?"):
        st.markdown("1. **Resumen** (esta página): la respuesta corta y el memo descargable.\n"
                    "2. **Explorador**: haga clic en un hexágono, escriba coordenadas o elija una estación de TransMilenio.\n"
                    "3. **Ranking**: ajuste filtros; seleccione una fila para ver el detalle y compare 2–3 zonas.\n"
                    "4. **Plan de estudio**: decida cuántas zonas visitar y cuánto presupuestar.\n"
                    "5. **Desempeño** y **Metodología**: evidencia, supuestos y límites para el banco y el comité.\n\n"
                    "Los supuestos de arriendo y canibalización se ajustan en la barra lateral y afectan todas las páginas.")
    if r.empty:
        st.warning("Con los supuestos actuales ninguna zona cumple los filtros. Ajuste el presupuesto o el radio en la barra lateral.")
    else:
        t = tabla_ranking(r, md, presupuesto, radio)
        cols = ["Pos.", "Zona", "Clase", "Puntaje", "Cafés hoy", "Esperados", "Riesgo", "Arriendo ref. (M/mes)", "Dist. mín. (m)", "Tienda cercana"]
        st.dataframe(t[cols].head(5), hide_index=True, column_config=COLCFG)
        with st.expander(f"Ver el ranking completo ({len(t)} zonas)"):
            st.dataframe(t, hide_index=True, column_config=COLCFG)
            st.caption("Filtros, comparador y detalle de cada zona en el módulo **Ranking**.")
