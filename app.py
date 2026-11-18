"""ZONA LIBRE: la interfaz de la aplicación CaféScore (adaptada desde la plantilla del curso).
Usa la ZONA FIJA (core/) para cargar el modelo, validar datos, predecir, decidir y explicar, y lee de mi_app.py el
título, el cliente y el pie de página. El pie de página se muestra siempre al final.

Para verla en su computador:   streamlit run app.py"""
import streamlit as st

from core import cargar_config, hay_modelo

config = cargar_config()
st.set_page_config(page_title=config["titulo"], page_icon="☕", layout="wide", initial_sidebar_state="expanded",
                   menu_items={"About": f"{config['titulo']} — {config['cliente']}. {config['descripcion']}."})

from cafescore import config as cfg, data, logic, nav, ui  # noqa: E402
from cafescore.views import (desempeno, evaluar, explorador, metodologia, plan, ranking,  # noqa: E402
                             resumen)

ui.estilos()


def pie_de_pagina():
    # Pie de página: debe quedar (atribuciones y advertencias de su caso, en mi_app.py)
    st.divider()
    st.caption(config["pie"])


# ---------------------------------------------------------------------------------------------
# Mientras no exporten el modelo o falten los artefactos, la app muestra la guía en lugar de fallar
# ---------------------------------------------------------------------------------------------
estado = data.estado_artefactos()
if not hay_modelo() or not all(estado.values()):
    ui.encabezado(config["cliente"], config["titulo"], config["descripcion"])
    st.info("Faltan archivos del modelo en la carpeta model/. La aplicación no muestra resultados inventados.")
    st.table({"Archivo": list(estado), "Disponible": ["Sí" if v else "No" for v in estado.values()]})
    st.markdown("Generen los artefactos con:")
    st.code("python pipeline/build_artifacts.py --datos /ruta/cafescore_data.csv", language="bash")
    pie_de_pagina()
    st.stop()

try:
    md = data.metadata()
    data.zonas(); data.metricas()
except data.ArtefactoFaltante as e:
    st.error(f"Artefacto inválido: {e}")
    pie_de_pagina()
    st.stop()

sup = md["supuestos"]
st.session_state.setdefault("presupuesto", float(sup["arriendo"]["presupuesto_max_millones"]))
st.session_state.setdefault("radio", int(sup["canibalizacion"]["radio_m"]))
st.session_state.setdefault("h3_sel", None)

# ---------------------------------------------------------------------------------------------
# Navegación
# ---------------------------------------------------------------------------------------------
st.logo(str(cfg.RAIZ / "assets" / "logo.svg"), size="large")
nav.PAGINAS.update({
    "resumen": st.Page(resumen.render, title="Resumen ejecutivo", icon=":material/space_dashboard:", url_path="resumen", default=True),
    "explorador": st.Page(explorador.render, title="Explorador geográfico", icon=":material/map:", url_path="explorador"),
    "ranking": st.Page(ranking.render, title="Ranking de oportunidades", icon=":material/format_list_numbered:", url_path="ranking"),
    "plan": st.Page(plan.render, title="Plan de estudio de campo", icon=":material/assignment:", url_path="plan"),
    "desempeno": st.Page(desempeno.render, title="Modelo vs. regla simple", icon=":material/query_stats:", url_path="desempeno"),
    "evaluar": st.Page(evaluar.render, title="Evaluar una zona nueva", icon=":material/edit_note:", url_path="evaluar"),
    "metodologia": st.Page(metodologia.render, title="Metodología y riesgos", icon=":material/menu_book:", url_path="metodologia"),
})
pg = st.navigation({"Decidir": [nav.PAGINAS[k] for k in ("resumen", "explorador", "ranking", "plan")],
                    "Evidencia": [nav.PAGINAS[k] for k in ("desempeno", "evaluar", "metodologia")]},
                   position="sidebar", expanded=True)

with st.sidebar:
    st.divider()
    st.markdown("**Supuestos de decisión**")
    st.slider("Arriendo máximo (COP M/mes)", 4.0, 20.0, step=0.5, key="presupuesto", format="%.1f M",
              help="Brief: Cereza puede pagar hasta COP 12 M al mes por un local de ~80 m². Se compara con el arriendo de "
                   "referencia (supuesto calibrado con el valor del suelo).")
    st.slider("Radio de posible canibalización (m)", 300, 3000, step=100, key="radio", format="%d m",
              help="Distancia en línea recta bajo la cual una zona nueva se marca por cercanía a una tienda actual. Supuesto ajustable.")
    st.caption(f"Valores por defecto: COP {sup['arriendo']['presupuesto_max_millones']:g} M y "
               f"{logic.fmt_m(sup['canibalizacion']['radio_m'])} m.")
    st.divider()
    st.caption(f"**{config['cliente']}** · {config['descripcion']}.\n\nModelo: {md['modelo']} · umbral {md['umbral']:.2f}\n\n"
               "Apoyo a la decisión: no garantiza rentabilidad ni autoriza inversiones.")

pg.run()

pie_de_pagina()
