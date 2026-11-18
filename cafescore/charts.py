"""Gráficos Altair con la paleta de la marca. Todos con títulos de ejes y unidades."""
from __future__ import annotations

import altair as alt
import pandas as pd

from . import config

FAMILIA_COLOR = {"Trivial": "#B8B2AA", "Regla": config.TOSTADO, "Modelo base (E1)": "#3D6FA8",
                 "Ensamble (final)": config.OLIVA}


MILES = "replace(datum.label, ',', '.')"


def _tema(ch):
    return ch.configure_axis(labelColor=config.ESPRESSO, titleColor=config.ESPRESSO, gridColor="#ECE6DE",
                             labelFontSize=12, titleFontSize=12, labelLimit=240).configure_view(stroke=None) \
             .configure_legend(labelColor=config.ESPRESSO, titleColor=config.ESPRESSO, orient="bottom")


def costos_metodos(tabla: list[dict]) -> alt.Chart:
    df = pd.DataFrame(tabla)
    df["lo"], df["hi"] = df["ic95"].str[0], df["ic95"].str[1]
    df["etq"] = df.apply(lambda r: r["metodo"] + ("  ★" if r["seleccionado"] else ""), axis=1)
    orden = df.sort_values("costo")["etq"].tolist()
    base = alt.Chart(df).encode(y=alt.Y("etq:N", sort=orden, title=None))
    barras = base.mark_bar(height=18, cornerRadiusEnd=3).encode(
        x=alt.X("costo:Q", title="Costo de errores en zonas de prueba (COP millones)", axis=alt.Axis(labelExpr=MILES)),
        color=alt.Color("familia:N", scale=alt.Scale(domain=list(FAMILIA_COLOR), range=list(FAMILIA_COLOR.values())),
                        title="Tipo de método"),
        tooltip=[alt.Tooltip("metodo:N", title="Método"), alt.Tooltip("costo:Q", title="Costo (M)", format=",.0f"),
                 alt.Tooltip("lo:Q", title="IC 2,5 %", format=",.0f"), alt.Tooltip("hi:Q", title="IC 97,5 %", format=",.0f")])
    err = base.mark_rule(color=config.ESPRESSO, strokeWidth=1.5).encode(x="lo:Q", x2="hi:Q")
    return _tema((barras + err).properties(height=340))


def diferencias(tabla: list[dict]) -> alt.Chart:
    df = pd.DataFrame([t for t in tabla if t.get("dif_vs_regla_ic95") and t["familia"] in ("Modelo base (E1)", "Ensamble (final)")])
    df["lo"], df["hi"] = df["dif_vs_regla_ic95"].str[0], df["dif_vs_regla_ic95"].str[1]
    df["veredicto"] = df.apply(lambda r: "Gana a la regla (IC < 0)" if r["hi"] < 0 else
                               ("Pierde con la regla (IC > 0)" if r["lo"] > 0 else "No concluyente (IC incluye 0)"), axis=1)
    escala = alt.Scale(domain=["Gana a la regla (IC < 0)", "No concluyente (IC incluye 0)", "Pierde con la regla (IC > 0)"],
                       range=["#2E7D4F", "#8A8178", config.CEREZA])
    base = alt.Chart(df).encode(y=alt.Y("metodo:N", title=None, sort=df.sort_values("dif_vs_regla")["metodo"].tolist()))
    rule = base.mark_rule(strokeWidth=3).encode(x=alt.X("lo:Q", title="Diferencia de costo frente a la regla simple (COP millones; negativo = ahorra)", axis=alt.Axis(labelExpr=MILES)),
                                                x2="hi:Q", color=alt.Color("veredicto:N", scale=escala, title=None))
    pt = base.mark_point(filled=True, size=110, shape="diamond").encode(
        x="dif_vs_regla:Q", color=alt.Color("veredicto:N", scale=escala, title=None),
        tooltip=[alt.Tooltip("metodo:N", title="Modelo"), alt.Tooltip("dif_vs_regla:Q", title="Diferencia (M)", format="+,.0f"),
                 alt.Tooltip("lo:Q", title="IC 2,5 %", format="+,.0f"), alt.Tooltip("hi:Q", title="IC 97,5 %", format="+,.0f")])
    cero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=config.ESPRESSO, strokeDash=[4, 3]).encode(x="x:Q")
    return _tema((rule + pt + cero).properties(height=190))


def curva_costo(curva: dict, umbral_sel: float) -> alt.Chart:
    filas = []
    for m in ("Regresión logística", "Árbol de decisión"):
        filas += [{"umbral": u, "costo": c, "modelo": m} for u, c in zip(curva["umbrales"], curva[m])]
    df = pd.DataFrame(filas)
    lineas = alt.Chart(df).mark_line(strokeWidth=2.2).encode(
        x=alt.X("umbral:Q", title="Umbral de probabilidad para estudiar una zona"),
        y=alt.Y("costo:Q", title="Costo en validación cruzada (COP millones)", scale=alt.Scale(zero=False), axis=alt.Axis(labelExpr=MILES)),
        color=alt.Color("modelo:N", scale=alt.Scale(range=["#3D6FA8", config.OLIVA]), title=None),
        tooltip=[alt.Tooltip("modelo:N"), alt.Tooltip("umbral:Q", format=".2f"), alt.Tooltip("costo:Q", format=",.0f")])
    regla = alt.Chart(pd.DataFrame({"y": [curva["regla_simple_ent"]], "t": ["Regla simple"]})).mark_rule(
        strokeDash=[5, 4], color=config.TOSTADO).encode(y="y:Q")
    u = alt.Chart(pd.DataFrame({"x": [umbral_sel]})).mark_rule(color=config.CEREZA).encode(x="x:Q")
    return _tema((lineas + regla + u).properties(height=300))


def importancia(df: pd.DataFrame, col: str, titulo_x: str, etiquetas: dict, err: str | None = None, n=10) -> alt.Chart:
    d = df.head(n).copy()
    d["var"] = d["variable"].map(lambda v: etiquetas.get(v, v))
    base = alt.Chart(d).encode(y=alt.Y("var:N", sort="-x", title=None))
    ch = base.mark_bar(color=config.TOSTADO, height=16, cornerRadiusEnd=3).encode(
        x=alt.X(f"{col}:Q", title=titulo_x), tooltip=[alt.Tooltip("var:N", title="Variable"), alt.Tooltip(f"{col}:Q", format=".4f")])
    if err:
        d["lo"], d["hi"] = d[col] - d[err], d[col] + d[err]
        ch = ch + alt.Chart(d).mark_rule(color=config.ESPRESSO).encode(y=alt.Y("var:N", sort="-x"), x="lo:Q", x2="hi:Q")
    return _tema(ch.properties(height=320))


def beeswarm(puntos: list, orden: list[str], etiquetas: dict) -> alt.Chart:
    df = pd.DataFrame(puntos, columns=["variable", "shap", "rango"])
    df = df[df["variable"].isin(orden)]
    df["var"] = df["variable"].map(lambda v: etiquetas.get(v, v))
    orden_lab = [etiquetas.get(v, v) for v in orden]
    ch = alt.Chart(df).mark_circle(size=14, opacity=0.6).encode(
        x=alt.X("shap:Q", title="Contribución SHAP al log-odds (izq. baja / der. sube el puntaje)"),
        y=alt.Y("var:N", sort=orden_lab, title=None),
        yOffset=alt.YOffset("jitter:Q"),
        color=alt.Color("rango:Q", scale=alt.Scale(range=["#3D6FA8", "#E9E2D8", config.CEREZA]),
                        title="Valor de la variable (percentil)"),
    ).transform_calculate(jitter="random()").properties(height=380)
    return _tema(ch)


def comparador(df: pd.DataFrame, var: str, titulo: str) -> alt.Chart:
    ch = alt.Chart(df).mark_bar(height=18, color=config.TOSTADO, cornerRadiusEnd=3).encode(
        y=alt.Y("zona:N", title=None), x=alt.X(f"{var}:Q", title=titulo),
        tooltip=[alt.Tooltip("zona:N"), alt.Tooltip(f"{var}:Q", format=",.2f")])
    return _tema(ch.properties(height=40 * len(df) + 30))


def calibracion(filas: list[dict]) -> alt.Chart:
    df = pd.DataFrame(filas)
    diag = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(strokeDash=[4, 3], color="#8A8178").encode(x="x:Q", y="y:Q")
    pts = alt.Chart(df).mark_circle(color=config.CEREZA, opacity=0.9).encode(
        x=alt.X("puntaje_medio:Q", title="Puntaje promedio del tramo", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
        y=alt.Y("tasa_cafe:Q", title="Zonas con café en el tramo", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
        size=alt.Size("zonas:Q", title="Zonas", scale=alt.Scale(range=[40, 600])),
        tooltip=[alt.Tooltip("tramo:N", title="Tramo"), alt.Tooltip("zonas:Q"), alt.Tooltip("puntaje_medio:Q", format=".0%"),
                 alt.Tooltip("tasa_cafe:Q", title="Con café", format=".0%")])
    return _tema((diag + pts).properties(height=300))


def barras_grupo(filas: list[dict], var: str, titulo: str, fmt: str = ",.0f") -> alt.Chart:
    df = pd.DataFrame(filas)
    ch = alt.Chart(df).mark_bar(color=config.TOSTADO, height=18, cornerRadiusEnd=3).encode(
        y=alt.Y("grupo:N", title=None, sort=None), x=alt.X(f"{var}:Q", title=titulo),
        tooltip=[alt.Tooltip("grupo:N"), alt.Tooltip("zonas:Q"), alt.Tooltip("fn:Q", title="FN"), alt.Tooltip("fp:Q", title="FP"),
                 alt.Tooltip(f"{var}:Q", format=fmt)])
    return _tema(ch.properties(height=40 * len(df) + 30))
