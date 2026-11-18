"""Reglas de negocio de la interfaz: filtros, ranking, alertas y textos. Sin Streamlit."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .geo import haversine_m

TIENDAS_DEF = ["Chapinero", "Teusaquillo", "Usaquén"]


def etiqueta(variable: str, etiquetas: dict) -> str:
    return etiquetas.get(variable, variable.replace("_", " "))


def factores(texto, etiquetas: dict) -> list[str]:
    if not isinstance(texto, str) or not texto:
        return []
    return [etiqueta(v, etiquetas) for v in texto.split("|")]


def estado_presupuesto(arriendo_ref: float, presupuesto: float) -> str:
    if pd.isna(arriendo_ref):
        return "Sin dato"
    return "Dentro del presupuesto" if arriendo_ref <= presupuesto else "Supera el presupuesto"


def alertas(fila: pd.Series, presupuesto: float, radio_m: float) -> list[str]:
    a = []
    if fila["dist_min_m"] < radio_m:
        a.append(f"Posible canibalización: {fmt_num(fila['dist_min_m'])} m de {fila['tienda_cercana']}")
    if fila["arriendo_ref_millones"] > presupuesto:
        a.append("Arriendo de referencia sobre el presupuesto")
    if fila["n_cafes"] >= 3:
        a.append(f"Competencia registrada: {int(fila['n_cafes'])} cafés en la celda")
    if fila["clase"] == "Oportunidad" and fila["n_cafes"] == 0:
        a.append("Sin cafés registrados: verificar en campo (puede haber negocios no registrados o uso no comercial)")
    return a


def siguiente_accion(fila: pd.Series, presupuesto: float, radio_m: float) -> str:
    c = fila["clase"]
    canib = fila["dist_min_m"] < radio_m
    caro = fila["arriendo_ref_millones"] > presupuesto
    if c == "Oportunidad":
        if caro:
            return "Confirmar arriendos reales de locales antes de pagar un estudio: el valor del suelo sugiere un arriendo alto."
        if canib:
            return (f"Revisar con el jefe de operaciones: queda cerca de la tienda de {fila['tienda_cercana']}. "
                    "Estudiar solo si el público objetivo es distinto.")
        return ("Candidata a estudio de campo (COP 20 M): verificar locales disponibles, uso del suelo comercial, "
                "flujo peatonal real y competencia no registrada.")
    if c == "En equilibrio":
        return "Segunda prioridad: considerar solo con un concepto de tienda diferenciado o si el estudio de una zona vecina lo justifica."
    if c == "Saturada":
        return "No priorizar: ya hay más cafés de los que el perfil de la zona sugiere; la competencia sería directa."
    return "No priorizar con la evidencia actual: el perfil de la zona no se parece al de las zonas que sostienen cafés."


def filtrar(df: pd.DataFrame, presupuesto=12.0, clases=None, puntaje=(0.0, 1.0), distancia=(0, 1e9),
            max_cafes=None, solo_presupuesto=True) -> pd.DataFrame:
    m = (df["puntaje"].between(*puntaje)) & (df["dist_min_m"].between(*distancia))
    if clases:
        m &= df["clase"].isin(clases)
    if solo_presupuesto:
        m &= df["arriendo_ref_millones"] <= presupuesto
    if max_cafes is not None:
        m &= df["n_cafes"] <= max_cafes
    return df[m]


def rankear(df: pd.DataFrame, n=10, separacion_m=600.0) -> pd.DataFrame:
    """Ordena por brecha (cafés faltantes) y puntaje; exige separación mínima entre zonas."""
    orden = df.sort_values(["brecha", "puntaje"], ascending=[False, False])
    elegidas = []
    for idx, fila in orden.iterrows():
        if separacion_m and elegidas:
            sel = orden.loc[elegidas]
            d = haversine_m(sel["lat"].values, sel["lon"].values, fila["lat"], fila["lon"])
            if (d < separacion_m).any():
                continue
        elegidas.append(idx)
        if len(elegidas) == n:
            break
    out = orden.loc[elegidas].copy()
    out.insert(0, "posicion", np.arange(1, len(out) + 1))
    return out


def referencia(fila: pd.Series) -> str:
    """Referencia legible de una celda: estación troncal más cercana y distancia."""
    d = fila.get("dist_tm_m")
    est = fila.get("tm_estacion")
    if isinstance(est, str) and pd.notna(d):
        return f"a {d / 1000:.1f} km de TM {est}" if d >= 1000 else f"a {d:.0f} m de TM {est}"
    return fila["h3"]


def nombre_corto(fila: pd.Series) -> str:
    est = fila.get("tm_estacion")
    return f"Cerca de TM {est}" if isinstance(est, str) else fila["h3"]


def razones_lista(fila: pd.Series) -> list[str]:
    """Razones de la zona fija (exportar.py / core.explicar), una por elemento."""
    t = fila.get("razones", "")
    return [r.strip() for r in str(t).split(" · ") if r.strip() and r.strip() != "nan"]


def razon_negocio(r: str) -> str:
    """'Oficinas a 300 m = 38 sube 3.5 pts' → 'Oficinas a 300 m = 38 sube el puntaje 3,5 puntos'."""
    import re
    m = re.match(r"^(.*) (sube|baja) ([\d.,]+) pts$", r)
    if not m:
        return r
    return f"{m.group(1)} {m.group(2)} el puntaje {m.group(3).replace('.', ',')} puntos"


def justificacion(fila: pd.Series, etiquetas: dict | None = None) -> str:
    base = f"Se esperan {fmt_num(fila['cafes_esperados'], 1)} cafés y hay {int(fila['n_cafes'])}"
    rz = [r for r in razones_lista(fila) if " sube " in r]
    return base + (f"; {razon_negocio(rz[0])}" if rz else "")


def fmt_num(x, dec=0, signo=False) -> str:
    """Número con formato colombiano: punto de miles y coma decimal."""
    s = f"{x:{'+' if signo else ''},.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_m(x) -> str:
    return fmt_num(x)


def fmt_cop(millones, dec=0) -> str:
    return f"COP {fmt_num(millones, dec)} M"


# --------------------------------------------------------------------------- riesgo (v2)
NIVELES_RIESGO = {"Bajo": "green", "Medio": "orange", "Alto": "red"}


def riesgo(fila: pd.Series, presupuesto: float, radio_m: float) -> tuple[str, int, list[str]]:
    """Calificación del riesgo de RECOMENDAR ESTUDIAR la zona (propuesta v1, transparente por puntos).

    No es riesgo crediticio ni probabilidad de quiebra de una tienda."""
    pts, motivos = 0, []
    est = fila.get("estabilidad_clase", 1.0)
    if est < 0.6:
        pts += 2; motivos.append(f"Clase inestable: se mantiene en {est * 100:.0f} % de los remuestreos")
    elif est < 0.8:
        pts += 1; motivos.append(f"Clase poco estable ({est * 100:.0f} % de los remuestreos)")
    ancho = fila.get("puntaje_p95", 0) - fila.get("puntaje_p05", 0)
    if ancho > 0.25:
        pts += 1; motivos.append(f"Puntaje incierto (intervalo de {ancho * 100:.0f} puntos)")
    a = fila["arriendo_ref_millones"]
    if a > presupuesto:
        pts += 2; motivos.append("Arriendo de referencia sobre el presupuesto")
    elif a > 0.8 * presupuesto:
        pts += 1; motivos.append("Arriendo de referencia cerca del tope")
    if fila["n_cafes"] >= 3:
        pts += 1; motivos.append(f"Competencia registrada ({int(fila['n_cafes'])} cafés)")
    if fila["dist_min_m"] < radio_m:
        pts += 1; motivos.append(f"Cerca de la tienda de {fila['tienda_cercana']}")
    if fila["clase"] == "Oportunidad" and fila["n_cafes"] == 0:
        pts += 1; motivos.append("Sin cafés registrados: verificar oferta no registrada y uso del suelo")
    nivel = "Bajo" if pts <= 1 else ("Medio" if pts <= 3 else "Alto")
    return nivel, pts, motivos


# --------------------------------------------------------------------------- escenario financiero (v2)
def escenario(arriendo_ref: float, margen=15.0, adecuacion=250.0) -> dict:
    """Escenario ilustrativo con los supuestos del brief; no es una proyección de la tienda."""
    neto = margen - arriendo_ref
    return {"margen_neto": neto, "meses_recuperacion": (adecuacion / neto) if neto > 0 else None}


def binom_al_menos(k: int, n: int, p: float) -> float:
    """P(X >= k) con X ~ Binomial(n, p)."""
    from math import comb
    return 1 - sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(min(k, n + 1)))


def estudios_necesarios(p: float, aptas=2, confianza=0.8, maximo=40) -> int | None:
    for n in range(aptas, maximo + 1):
        if binom_al_menos(aptas, n, p) >= confianza:
            return n
    return None


def distancias_entre(sel: pd.DataFrame) -> list[tuple[str, str, float]]:
    out = []
    filas = list(sel.iterrows())
    for i in range(len(filas)):
        for j in range(i + 1, len(filas)):
            a, b = filas[i][1], filas[j][1]
            out.append((a["h3"], b["h3"], float(haversine_m(a["lat"], a["lon"], b["lat"], b["lon"]))))
    return out
