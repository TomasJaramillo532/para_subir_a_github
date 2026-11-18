"""Módulo 4 — Desempeño, validación y valor del modelo."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import charts, data, logic, sim, ui
from .plan import boot_matrix


def _veredicto(lo, hi):
    if hi < 0:
        return "gana", "le gana a la regla con evidencia: todo el intervalo de la diferencia es negativo"
    if lo > 0:
        return "pierde", "pierde con la regla: todo el intervalo es positivo"
    return "empate", "no se puede afirmar que le gane: el intervalo de la diferencia incluye el cero"


def render():
    m, md = data.metricas(), data.metadata()
    sel = m["seleccionado"]
    fs, fr = data.fila_metodo(m, sel), data.fila_metodo(m, "Regla simple")
    pt = m["particion"]
    ui.encabezado("Módulo 4 · Desempeño y valor", "¿Vale la pena usar el modelo?",
                  f"Todo se mide en {pt['celdas_prueba']} zonas de {pt['bloques_prueba']} bloques de prueba que ningún modelo vio al "
                  f"entrenarse ni al elegir parámetros o umbral. Intervalos de 95 % con {logic.fmt_m(pt['bootstrap'])} remuestreos de bloques.")

    tabs = st.tabs(["Comparación de métodos", "Errores y umbral", "Simulador de supuestos", "Dónde se equivoca",
                    "Explicabilidad", "Validación con aperturas", "Valor del mapa"])

    # ---------------- A + D ----------------
    with tabs[0]:
        tipo, txt = _veredicto(*fs["dif_vs_regla_ic95"])
        lo, hi = fs["dif_vs_regla_ic95"]
        k = st.columns(4)
        k[0].metric("Costo del modelo ★", logic.fmt_cop(fs["costo"]))
        k[1].metric("Costo de la regla simple", logic.fmt_cop(fr["costo"]))
        k[2].metric("Diferencia (modelo − regla)", logic.fmt_cop(fs["dif_vs_regla"]),
                    help="Negativo = el modelo comete errores más baratos que la regla.")
        k[3].metric("IC 95 % diferencia", f"{logic.fmt_num(lo, signo=True)} a {logic.fmt_num(hi, signo=True)} M")
        (st.success if tipo == "gana" else st.warning)(
            f"**Conclusión honesta:** el modelo seleccionado ({sel}) {txt}. "
            + ("Con la evidencia disponible, **la regla simple basta para preseleccionar zonas**; el mapa aporta orden, "
               "explicación y la clasificación de saturación que la regla no da." if tipo != "gana" else ""), icon="⚖️")

        gb = data.fila_metodo(m, "Gradient boosting")
        if gb and gb["dif_vs_regla_ic95"][1] < 0 and sel != "Gradient boosting":
            ui.nota(f"<b>Nota metodológica.</b> En prueba, el gradient boosting cuesta {logic.fmt_cop(gb['costo'])} y su intervalo "
                    f"frente a la regla ({logic.fmt_num(gb['dif_vs_regla_ic95'][0], signo=True)} a {logic.fmt_num(gb['dif_vs_regla_ic95'][1], signo=True)} M) no incluye el cero. "
                    f"Sin embargo, en validación cruzada dentro de entrenamiento costó {logic.fmt_m(gb['costo_cv'])} M frente a "
                    f"{logic.fmt_m(fs['costo_cv'])} M de la {sel.lower()}, y la regla del equipo es elegir con entrenamiento. "
                    "Cambiar de modelo por su resultado en prueba sería usar la prueba para elegir, así que se mantiene la selección "
                    "y este resultado se reporta como evidencia favorable a los ensambles, no como prueba independiente.")

        st.altair_chart(charts.costos_metodos(m["tabla_prueba"]), width="stretch")
        st.caption("Barras: costo de los errores (60 M por zona con café descartada + 20 M por zona sin café estudiada). "
                   "Líneas: intervalo de 95 %. ★ modelo seleccionado por costo en validación cruzada.")
        st.altair_chart(charts.diferencias(m["tabla_prueba"]), width="stretch")

        df = pd.DataFrame(m["tabla_prueba"])
        tabla = pd.DataFrame({
            "Método": df["metodo"] + df["seleccionado"].map({True: " ★", False: ""}), "Tipo": df["familia"],
            "Costo (M)": df["costo"], "IC 95 %": df["ic95"].map(lambda v: f"{logic.fmt_m(v[0])} – {logic.fmt_m(v[1])}"),
            "Zonas a estudiar": df["zonas_estudiar"], "FN": df["fn"], "FP": df["fp"],
            "Sensibilidad": df["sensibilidad"], "Precisión": df["precision"], "AUC": df["auc"],
            "Umbral": df["umbral"], "Costo CV (M)": df["costo_cv"], "Parámetros": df["parametros"]})
        st.dataframe(tabla.sort_values("Costo (M)"), hide_index=True, column_config={
            "Sensibilidad": st.column_config.NumberColumn(format="%.2f"), "Precisión": st.column_config.NumberColumn(format="%.2f"),
            "AUC": st.column_config.NumberColumn(format="%.3f"), "Umbral": st.column_config.NumberColumn(format="%.2f")})
        st.caption("Sensibilidad: de las zonas con café, cuántas reconoce. Precisión: de las que manda a estudiar, cuántas tienen café "
                   "(una precisión baja no es necesariamente mala: algunos ‘falsos positivos’ son justo los espacios en blanco que se buscan). "
                   "AUC: qué tan bien ordena las zonas. Costo CV: costo en validación cruzada por bloques dentro de entrenamiento, con el que se eligió.")
        with st.expander("Verificación de reproducibilidad frente al informe de la Entrega 1"):
            st.dataframe(pd.DataFrame(m["verificacion_e1"]), hide_index=True)
            st.caption("Los costos en prueba se recalcularon desde los datos con la semilla 2559 y coinciden exactamente con el informe.")

    # ---------------- B + C ----------------
    with tabs[1]:
        c = md["costos"]
        a, b = st.columns(2)
        with a.container(border=True):
            st.markdown(f"**Falso negativo · COP {c['FN']} M**")
            st.write("El modelo descarta una zona que sí sostiene cafés: Cereza deja de ganar el margen mientras encuentra otra zona.")
        with b.container(border=True):
            st.markdown(f"**Falso positivo · COP {c['FP']} M**")
            st.write("El modelo manda a estudiar una zona que hoy no tiene cafés: Cereza paga un estudio de campo. A veces ese estudio "
                     "descubre justo la oportunidad buscada.")
        st.caption(f"Como un falso negativo cuesta 3 veces más, el umbral teórico es {c['FP']}/({c['FP']}+{c['FN']}) = 0,25 y no 0,5. "
                   "Estos costos son de clasificación: no son la rentabilidad de una tienda.")

        st.markdown(f"##### Matriz de confusión · {sel} (umbral {fs['umbral']:.2f})")
        g = st.columns(2)
        celdas = [("Real sin café · no estudiar", fs["vn"], "Verdadero negativo: se ahorra un estudio innecesario.", 0),
                  ("Real sin café · estudiar", fs["fp"], "Falso positivo: estudio de 20 M; puede revelar un espacio en blanco.", c["FP"]),
                  ("Real con café · no estudiar", fs["fn"], "Falso negativo: oportunidad perdida de 60 M. El error caro.", c["FN"]),
                  ("Real con café · estudiar", fs["vp"], "Verdadero positivo: zona con perfil y cafés que el modelo reconoce.", 0)]
        for i, (t, n, d, cu) in enumerate(celdas):
            with g[i % 2].container(border=True):
                st.metric(t, f"{n} zonas", delta=f"{logic.fmt_cop(n * cu)}" if cu else "sin costo", delta_color="off")
                st.caption(d)
        st.markdown("##### Costo según el umbral (validación cruzada en entrenamiento)")
        st.altair_chart(charts.curva_costo(m["curva_costo"], m["umbral_seleccionado"]), width="stretch")
        st.caption("Línea punteada café: regla simple en entrenamiento. Línea roja: umbral elegido.")

        cn = m["conteo"]
        with st.expander("Modelo de conteo (número de cafés esperados) — necesario para la brecha"):
            st.write(f"Elegido por devianza de Poisson en validación cruzada por bloques: **{cn['modelo']} ({cn['parametros']})**.")
            st.dataframe(pd.DataFrame([
                {"Métrica en prueba": "Devianza de Poisson", "Modelo": round(cn["devianza_prueba"], 3), "Promedio de entrenamiento": round(cn["devianza_media"], 3)},
                {"Métrica en prueba": "Error absoluto medio (cafés)", "Modelo": round(cn["mae_prueba"], 3), "Promedio de entrenamiento": round(cn["mae_media"], 3)},
                {"Métrica en prueba": "Cafés totales", "Modelo": round(cn["cafes_predichos_prueba"], 1), "Promedio de entrenamiento": cn["cafes_reales_prueba"]},
            ]).rename(columns={"Promedio de entrenamiento": "Referencia (media / real)"}), hide_index=True)
            st.caption("La brecha usa predicciones fuera de bloque de este modelo; la brecha nunca es una variable de entrada.")


    # ---------------- Simulador ----------------
    with tabs[2]:
        st.markdown("**¿Qué cambia si Cereza discute los costos del caso?** Mueva los costos: el umbral del modelo y los cortes de "
                    "la regla se vuelven a elegir con los datos de entrenamiento, y la comparación se mide otra vez en las mismas "
                    "zonas de prueba con 1.000 remuestreos de bloques.")
        a, b = st.columns(2)
        cfn = a.slider("Costo de descartar una zona que sí tiene café (FN, COP M)", 10, 150, 60, 5)
        cfp = b.slider("Costo de estudiar una zona sin café (FP, COP M)", 5, 60, 20, 5)
        res = sim.simular(m["simulador"], cfn, cfp, boot_matrix(m["simulador"]["bloques"]))
        k = st.columns(4)
        k[0].metric("Umbral elegido (entrenamiento)", f"{res['umbral']:.2f}", help=f"Teórico: {res['umbral_teorico']:.2f}")
        k[1].metric("Costo del modelo", logic.fmt_cop(res["modelo"]["costo"]),
                    help=f"FN {res['modelo']['fn']} · FP {res['modelo']['fp']} · IC {logic.fmt_m(res['modelo']['ic'][0])}–{logic.fmt_m(res['modelo']['ic'][1])}")
        k[2].metric("Costo de la regla", logic.fmt_cop(res["regla"]["costo"]),
                    help=f"Cortes: comercio ≥ {res['corte_comercio']:.0f}, suelo ≥ {logic.fmt_m(res['corte_suelo'])} · FN {res['regla']['fn']} · FP {res['regla']['fp']}")
        lo, hi = res["dif_ic"]
        k[3].metric("Modelo − regla", logic.fmt_cop(res["dif"]),
                    delta=f"IC {logic.fmt_num(lo, signo=True)} a {logic.fmt_num(hi, signo=True)}", delta_color="off", delta_arrow="off")
        tipo, txt = _veredicto(lo, hi)
        (st.success if tipo == "gana" else st.info)(f"Con FN = {cfn} M y FP = {cfp} M, el modelo {txt}.", icon="🧮")
        st.caption(f"Referencias triviales: estudiar todas {logic.fmt_cop(res['todas']['costo'])} · no estudiar ninguna "
                   f"{logic.fmt_cop(res['ninguna']['costo'])}. Con los costos del caso (60/20) el simulador reproduce exactamente la tabla oficial.")

    # ---------------- Errores ----------------
    with tabs[3]:
        er = m["errores"]
        st.markdown("**Dónde se equivoca el modelo** (solo zonas de prueba, modelo seleccionado, umbral 0,25).")
        a, b = st.columns(2)
        with a:
            st.markdown("###### Costo de errores por zona, según tipo de zona")
            st.altair_chart(charts.barras_grupo(er["por_segmento"], "costo_por_zona", "COP M por zona de prueba", ",.1f"), width="stretch")
        with b:
            st.markdown("###### Según el valor del suelo (quintiles de la ciudad)")
            st.altair_chart(charts.barras_grupo(er["por_suelo"], "costo_por_zona", "COP M por zona de prueba", ",.1f"), width="stretch")
        peor = max(er["por_suelo"], key=lambda x: x["costo_por_zona"])
        fp_tot = sum(x["fp"] for x in er["por_suelo"]); fn_tot = sum(x["fn"] for x in er["por_suelo"])
        fp_medio = sum(x["fp"] for x in er["por_suelo"] if x["grupo"] in ("Q3", "Q4"))
        barato = next(x for x in er["por_suelo"] if x["grupo"].startswith("Q1"))
        ui.nota(f"<b>Lectura para Cereza.</b> El costo por zona es mayor en suelo medio ({peor['grupo']}: "
                f"{logic.fmt_num(peor['costo_por_zona'], 1)} M por zona). Allí están {fp_medio} de los {fp_tot} falsos positivos: "
                "zonas con perfil de demanda pero sin café registrado, justo las que hay que verificar en campo (algunas serán "
                "espacios en blanco reales; otras no tendrán locales o tendrán cafés no registrados). En el suelo más barato hay "
                f"{barato['fn']} de los {fn_tot} falsos negativos: cafés de barrio en zonas con poca actividad registrada, que el modelo "
                "no reconoce. El mapa de errores está en el Explorador (capa «Errores del modelo en zonas de prueba»).")
        st.markdown("###### Tipos de zona (técnica de descubrimiento: k-means, k = 4)")
        acciones = {
            "Núcleo de oficinas y universidades": "Mercado probado y muy competido: entrar solo con un formato diferenciado (para llevar, mañana y tarde).",
            "Corredor comercial denso": "Destino de cafés: competir por experiencia; arriendo alto; priorizar solo celdas con brecha positiva.",
            "Barrio mixto": "Donde están la mayoría de las oportunidades: concepto de barrio; validar flujo peatonal real.",
            "Residencial de baja actividad": "No priorizar: casi no hay cafés ni generadores de demanda.",
        }
        z = data.zonas()
        seg = pd.DataFrame(m["segmentos"])
        seg["oportunidades"] = seg["nombre"].map(z[z.clase == "Oportunidad"]["segmento"].value_counts()).fillna(0).astype(int)
        st.dataframe(pd.DataFrame({"Tipo de zona": seg["nombre"], "Zonas": seg["celdas"], "% con café": seg["tasa_cafe"],
                                   "Comercio a 300 m (prom.)": seg["comercio"].round(0), "Oficinas (prom.)": seg["oficinas"].round(1),
                                   "Suelo mediano (COP/m²)": seg["suelo"], "Zonas de oportunidad": seg["oportunidades"],
                                   "Acción para Cereza": seg["nombre"].map(acciones)}), hide_index=True,
                     column_config={"% con café": st.column_config.NumberColumn(format="percent"),
                                    "Suelo mediano (COP/m²)": st.column_config.NumberColumn(format="localized"),
                                    "Acción para Cereza": st.column_config.TextColumn(width="large")})
        st.caption("k = 4 según el método del codo del cuaderno. Los segmentos describen la ciudad; no son entradas del modelo.")
        st.markdown("###### ¿Se puede leer el puntaje como probabilidad? (calibración fuera de bloque)")
        st.altair_chart(charts.calibracion(m["calibracion"]), width="stretch")
        st.caption("Cada punto agrupa zonas por tramo de puntaje. Cerca de la diagonal = el puntaje coincide con la proporción real de "
                   "zonas con café. Es la probabilidad de que la zona tenga café, no de que una tienda tenga éxito.")

    # ---------------- E ----------------
    with tabs[4]:
        et = md["etiquetas"]
        shap_df = pd.DataFrame(m["importancia_shap"])
        perm_df = pd.DataFrame(m["importancia_permutacion"])
        top = [etiqueta for etiqueta in shap_df["variable"].head(3)]
        st.markdown(f"Las variables que más mueven el puntaje del modelo son **{', '.join(et.get(v, v) for v in top)}**. "
                    "En lenguaje de negocio: las zonas con perfil de café son las de calle activa (belleza, entretenimiento, "
                    "comercio), con oficinas y paraderos del SITP alrededor. El flujo de la estación troncal casi no pesa.")
        a, b = st.columns(2)
        with a:
            st.markdown("##### SHAP · contribución media absoluta")
            st.altair_chart(charts.importancia(shap_df, "shap_abs_medio", "Contribución media |SHAP| (log-odds)", et), width="stretch")
        with b:
            st.markdown("##### Importancia por permutación (AUC)")
            st.altair_chart(charts.importancia(perm_df, "importancia", "Caída del AUC al desordenar la variable", et, err="de"), width="stretch")
        st.markdown("##### Dirección del efecto (SHAP por zona de prueba)")
        st.altair_chart(charts.beeswarm(m["beeswarm"], shap_df["variable"].head(10).tolist(), et), width="stretch")
        ui.nota("<b>Cómo leerlo.</b> Cada punto es una zona de prueba. Rojo = valor alto de la variable; a la derecha sube el puntaje. "
                "Las caídas de AUC por permutación son pequeñas porque las variables de actividad están muy correlacionadas: al "
                "desordenar una, las demás cubren su información. <b>Son asociaciones, no causas</b>: que haya oficinas cerca de "
                "muchos cafés no garantiza que un café nuevo junto a unas oficinas venda.")
        st.caption(f"Modelo explicado: {sel}. SHAP lineal exacto (verificado contra la librería shap; error máximo "
                   f"{m.get('shap_verificacion_error_max') or 0:.1e}).")

    # ---------------- F ----------------
    with tabs[5]:
        v = m["validacion_aperturas"]
        if v.get("estado") == "completa":
            k = st.columns(3)
            k[0].metric("Tasa de apertura · zonas Oportunidad (abril)", f"{v['tasa_oportunidad'] * 100:.1f} %", help=f"{v['n_oportunidad']} zonas")
            k[1].metric("Tasa de apertura · comparables", f"{v['tasa_comparables'] * 100:.1f} %", help=f"{v['n_comparables']} zonas")
            k[2].metric("Diferencia (IC 95 %)", f"{v['dif'] * 100:+.1f} pp", f"{v['dif_ic95'][0] * 100:+.1f} a {v['dif_ic95'][1] * 100:+.1f} pp", delta_color="off")
            st.dataframe(pd.DataFrame(v["por_clase"]), hide_index=True)
            st.caption(v.get("nota", ""))
        else:
            ui.pendiente("Validación temporal pendiente: falta el archivo de aperturas",
                         "El equipo docente entrega un archivo con los cafés de cada celda en abril de 2026 y las aperturas entre abril y "
                         "septiembre. Cuando esté disponible se ejecuta <code>python pipeline/build_artifacts.py --datos … --aperturas …</code> "
                         "y esta sección mostrará automáticamente si las zonas clasificadas como Oportunidad <b>con la oferta de abril</b> "
                         "recibieron más aperturas que zonas comparables (las demás que el modelo manda a estudiar).<br><br>"
                         "<b>Formato esperado:</b> <code>h3, n_cafes_abril, n_aperturas</code>. "
                         "No se muestra ninguna tasa de acierto mientras tanto.")
            st.caption("Orden temporal: los puntajes no usan cafés (el target no es entrada), así que solo cambia la brecha, que se "
                       "recalcula con los cafés de abril para no usar información futura.")

    # ---------------- G ----------------
    with tabs[6]:
        val = m["valor"]
        st.markdown(f"**Pregunta:** si Cereza necesita encontrar **{val['zonas_aptas_objetivo']} zonas aptas**, ¿cuántos estudios de "
                    f"COP {val['costo_estudio_millones']} M necesita con cada método?")
        k = st.columns(4)
        k[0].metric("Estudios con el modelo", f"{val['estudios_modelo']:.1f}", help=f"2 / precisión {val['precision_modelo']:.3f}")
        k[1].metric("Estudios con la regla", f"{val['estudios_regla']:.1f}", help=f"2 / precisión {val['precision_regla']:.3f}")
        k[2].metric("Ahorro frente a la regla", logic.fmt_cop(val["ahorro_vs_regla"], 1))
        lo, hi = val["ahorro_vs_regla_ic95"]
        k[3].metric("IC 95 % del ahorro", f"{logic.fmt_num(lo, 1, True)} a {logic.fmt_num(hi, 1, True)} M")
        st.warning(f"El ahorro esperado frente a la regla es de unos {logic.fmt_cop(val['ahorro_vs_regla'], 1)} y su intervalo incluye el "
                   "cero: **en número de estudios, el mapa no es mejor que la regla simple de forma demostrable**. Frente a elegir "
                   f"al azar ({val['estudios_azar']:.1f} estudios) los dos métodos sí ahorran unos "
                   f"{logic.fmt_cop((val['estudios_azar'] - val['estudios_modelo']) * val['costo_estudio_millones'])}.", icon="📊")
        st.dataframe(pd.DataFrame([
            {"Supuesto": "Costo de estudiar una zona", "Valor": "COP 20 M (brief)"},
            {"Supuesto": "Zonas aptas requeridas", "Valor": "2 (las dos aperturas de 2027)"},
            {"Supuesto": "Zona ‘apta’", "Valor": "Tiene al menos un café hoy (proxy del target); no mide rentabilidad"},
            {"Supuesto": "Tasa de acierto", "Valor": "Precisión de cada método en las zonas de prueba"},
            {"Supuesto": "Estudios necesarios", "Valor": "2 / precisión (valor esperado)"},
            {"Supuesto": "Incertidumbre", "Valor": "Bootstrap de bloques de prueba (mismas muestras para ambos métodos)"},
        ]), hide_index=True)
        ui.nota("<b>Limitaciones.</b> El cálculo usa ‘hay café hoy’ como señal de zona apta; una zona apta puede no tener locales "
                "disponibles y una zona sin cafés puede ser una oportunidad real. El ejemplo del brief (3 vs 6 de 10) es ilustrativo y "
                "no se usa. Una buena ubicación no garantiza que una tienda funcione: precio, servicio y marca también deciden.")
