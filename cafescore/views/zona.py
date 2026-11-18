"""Panel de detalle de una zona (compartido por Explorador y Ranking)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import data, logic, reports, ui
import core


def panel(fila: pd.Series, md: dict, presupuesto: float, radio: float):
    et = md["etiquetas"]
    st.markdown(f"#### {logic.referencia(fila)}")
    st.caption(f"Identificador H3 · `{fila['h3']}` · {fila['segmento']}")
    ui.badge_clase(fila["clase"])

    ui.stats([
        ("Puntaje", f"{fila['puntaje'] * 100:.0f} %", "Probabilidad fuera de bloque de que una zona con este perfil tenga café. "
                                                     "No es la probabilidad de éxito de una tienda."),
        ("Cafés hoy", f"{int(fila['n_cafes'])}", "Overture Maps, septiembre de 2026"),
        ("Esperados", logic.fmt_num(fila['cafes_esperados'], 1), "Modelo de conteo, fuera de bloque"),
        ("Brecha", logic.fmt_num(fila['brecha'], 1, True), "Esperados − observados. Positivo: faltan cafés frente al perfil."),
    ])
    st.caption(f"Intervalo del puntaje (90 %): {fila['puntaje_p05'] * 100:.0f}–{fila['puntaje_p95'] * 100:.0f} % · "
               f"la clase se mantiene en {fila['estabilidad_clase'] * 100:.0f} % de los remuestreos · "
               f"sobremesa urbana {fila['isu']:.0f}/100 (propuesta). El puntaje describe el perfil de la zona; "
               "no es la probabilidad de éxito de una tienda nueva.")

    nivel, pts, motivos = logic.riesgo(fila, presupuesto, radio)
    with st.container(border=True):
        st.badge(f"Riesgo de la recomendación: {nivel}", color=logic.NIVELES_RIESGO[nivel], icon=":material/shield:")
        st.caption(("; ".join(motivos) if motivos else "Sin alertas de riesgo.") +
                   f" · {pts} punto(s). Es el riesgo de recomendar estudiar la zona, no una calificación crediticia.")

    st.markdown("**Razones principales, en lenguaje de negocio**")
    rz = logic.razones_lista(fila)
    if rz:
        st.markdown("\n".join(f"- {'▲' if ' sube ' in r else '▼'} {logic.razon_negocio(r)}" for r in rz))
    else:
        st.markdown("- Ninguna variable mueve el puntaje frente a una zona típica.")
    st.caption("Cuánto cambia el puntaje si cada variable tomara el valor de una zona típica de Bogotá (zona fija de la "
               "plantilla). Dicen de qué depende la predicción, no qué pasaría si algo cambiara: son asociaciones, no causas.")

    st.markdown("**Costo y proximidad**")
    ui.kv([
        ("Valor del suelo", f"COP {logic.fmt_m(fila['valor_suelo_m2'])} por m²"),
        ("Arriendo de referencia 80 m² (supuesto)", f"{logic.fmt_cop(fila['arriendo_ref_millones'], 1)}/mes · "
                                                    f"{logic.estado_presupuesto(fila['arriendo_ref_millones'], presupuesto).lower()}"),
        *[(f"Distancia a {t}", f"{logic.fmt_m(fila[f'dist_{t}'])} m") for t in logic.TIENDAS_DEF],
        ("Tienda más cercana", f"{fila['tienda_cercana']} · {logic.fmt_m(fila['dist_min_m'])} m"),
    ])
    st.caption("Distancias en línea recta (Haversine) desde el centro de la celda; no son distancias de conducción.")

    for a in logic.alertas(fila, presupuesto, radio):
        st.warning(a, icon="⚠️")
    st.info("**Siguiente acción:** " + logic.siguiente_accion(fila, presupuesto, radio), icon="➡️")

    st.download_button("Descargar ficha para estudio de campo", reports.ficha(fila, md, presupuesto, radio).encode("utf-8"),
                       f"ficha_{fila['h3']}.html", "text/html", width="stretch", key=f"ficha_{fila['h3']}",
                       help="Documento imprimible (abrir en el navegador y guardar como PDF).")
    with st.expander("Detalle técnico: evaluación en vivo con la zona fija (core/)"):
        try:
            meta, modelo = data.modelo()
            cols = [c["nombre"] for c in meta["columnas"]]
            datos, errores, avisos = core.validar(pd.DataFrame([fila[cols].to_dict()]), meta)
            for e in errores:
                st.error(e)
            for a in avisos:
                st.warning(a)
            if not errores:
                r = core.evaluar(modelo, meta, datos)[0]
                st.write(f"Probabilidad de {meta['evento']} con el modelo exportado: **{r['probabilidad']:.0%}** · "
                         f"recomendación: **{r['decision']}** (umbral {meta['umbrales'][0]:.2f}).")
                for x in r["razones"]:
                    st.markdown(f"- {core.texto_razon(x, meta)}")
                st.caption("El modelo exportado se entrenó con los bloques de entrenamiento: para esas zonas su probabilidad es "
                           f"optimista. Por eso el mapa usa el puntaje fuera de bloque ({fila['puntaje']:.0%}). "
                           f"Partición de esta zona: {fila['particion']}.")
        except Exception as e:  # noqa: BLE001
            st.error(f"No se pudo evaluar la zona con el modelo: {e}")
