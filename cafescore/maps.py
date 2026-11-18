"""Mapas con pydeck (capa H3 nativa, sin token: mapa base CARTO)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pydeck as pdk

from . import config
from .config import CLASES

RAMPA_PUNTAJE = ["#F6EFE6", "#E8CFAE", "#D3A270", "#B4733F", "#865025", "#4E2C17"]
RAMPA_SUELO = ["#F1F3EC", "#CFD9C6", "#A5BA98", "#7A9970", "#52744C", "#2F4A2C"]
RAMPA_CAFES = ["#F7F1EA", "#EBCFC4", "#D99D90", "#C06A61", "#9B3D3C", "#6A1E25"]
RAMPA_BRECHA = ["#B23A2E", "#E08E79", "#F4EEE6", "#8DC29B", "#2E7D4F"]  # saturada ← 0 → oportunidad
SEGMENTOS = {"Núcleo de oficinas y universidades": [91, 64, 51], "Corredor comercial denso": [166, 58, 69],
             "Barrio mixto": [101, 123, 98], "Residencial de baja actividad": [196, 190, 181]}


def _ascii(texto: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def _hex2rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _rampa(valores, colores, vmin, vmax):
    v = np.clip((np.asarray(valores, float) - vmin) / (vmax - vmin + 1e-12), 0, 1)
    pos = np.linspace(0, 1, len(colores))
    rgb = np.array([_hex2rgb(c) for c in colores], float)
    out = np.stack([np.interp(v, pos, rgb[:, k]) for k in range(3)], axis=1)
    return out.round().astype(int).tolist()


CAPAS = {
    "Clasificación de zonas": "clase",
    "Puntaje del modelo": "puntaje",
    "Brecha de oferta (esperados − observados)": "brecha",
    "Cafés observados": "n_cafes",
    "Valor del suelo": "valor_suelo_m2",
    "Arriendo de referencia (supuesto)": "arriendo_ref_millones",
    "Tipo de zona (segmentación)": "segmento",
    "Índice de sobremesa urbana (propuesta)": "isu",
    "Estabilidad de la clase": "estabilidad_clase",
    "Errores del modelo en zonas de prueba": "error_prueba",
}
ERRORES = {"Acierto: con café": [46, 125, 79], "Acierto: descartada": [200, 196, 190],
           "Falso positivo": [224, 160, 60], "Falso negativo": [166, 58, 69]}

EXPLICACION = {
    "Clasificación de zonas": "Combina el puntaje del clasificador y la brecha del modelo de conteo (definiciones en Metodología).",
    "Puntaje del modelo": "Probabilidad de que la zona tenga al menos un café según su perfil, calculada con un modelo que no vio el bloque de la zona. No es la probabilidad de éxito de una tienda nueva.",
    "Brecha de oferta (esperados − observados)": "Cafés que el modelo de conteo espera menos cafés registrados (Overture, sept. 2026). Positivo = faltan cafés frente al perfil; negativo = sobran.",
    "Cafés observados": "Cafés registrados en la celda (Overture Maps, septiembre de 2026). Puede omitir negocios no registrados.",
    "Valor del suelo": "Valor de referencia mediano del m² de suelo, Catastro de Bogotá 2026. No es el arriendo.",
    "Arriendo de referencia (supuesto)": "Estimación proporcional al valor del suelo, anclada en el promedio de Chapinero Central (COP 6,5 M por 80 m²). Supuesto, no dato observado.",
    "Tipo de zona (segmentación)": "Segmentos k-means (k = 4) sobre suelo, comercio, oficinas, universidades y entretenimiento.",
    "Índice de sobremesa urbana (propuesta)": "Promedio de percentiles de oficinas, universidades y espacios de permanencia (parques, centros comerciales) a 300 m. Propuesta operativa del concepto de la Entrega 1; no es entrada del modelo.",
    "Estabilidad de la clase": "Porcentaje de 100 remuestreos de bloques (modelos que no vieron la zona) en que la zona conserva su clase. Bajo = clasificación incierta.",
    "Errores del modelo en zonas de prueba": "Solo los 22 bloques de prueba: dónde acertó y dónde se equivocó el modelo seleccionado (umbral 0,25). El resto de la ciudad se atenúa.",
}


def colorear(df: pd.DataFrame, capa: str, presupuesto: float = 12.0) -> tuple[pd.DataFrame, dict]:
    """Devuelve la tabla con una columna 'color' [r,g,b,a] y la especificación de leyenda."""
    d = df.copy()
    alfa = 175
    if capa == "Clasificación de zonas":
        d["color"] = d["clase"].map(lambda c: CLASES[c]["rgb"] + [alfa])
        ley = {"tipo": "clases"}
    elif capa == "Puntaje del modelo":
        d["color"] = [c + [alfa] for c in _rampa(d["puntaje"], RAMPA_PUNTAJE, 0, 1)]
        ley = {"tipo": "continua", "colores": RAMPA_PUNTAJE, "etiquetas": ["0 %", "25 %", "50 %", "75 %", "100 %"],
               "titulo": "Probabilidad de que la zona tenga café (perfil)"}
    elif capa.startswith("Brecha"):
        d["color"] = [c + [alfa] for c in _rampa(d["brecha"], RAMPA_BRECHA, -3, 3)]
        ley = {"tipo": "continua", "colores": RAMPA_BRECHA, "etiquetas": ["≤ −3 (sobran)", "0", "≥ +3 (faltan)"],
               "titulo": "Brecha en número de cafés"}
    elif capa == "Cafés observados":
        d["color"] = [c + [alfa] for c in _rampa(np.log1p(d["n_cafes"]), RAMPA_CAFES, 0, np.log1p(10))]
        ley = {"tipo": "continua", "colores": RAMPA_CAFES, "etiquetas": ["0", "1", "3", "10+"],
               "titulo": "Cafés registrados en la celda"}
    elif capa == "Valor del suelo":
        lv = np.log10(d["valor_suelo_m2"].clip(lower=2e5))
        d["color"] = [c + [alfa] for c in _rampa(lv, RAMPA_SUELO, np.log10(2e5), np.log10(1e7))]
        ley = {"tipo": "continua", "colores": RAMPA_SUELO, "etiquetas": ["≤ 0,2 M", "1 M", "3 M", "≥ 10 M"],
               "titulo": "Valor del suelo (COP por m², escala logarítmica)"}
    elif capa.startswith("Arriendo"):
        d["color"] = [c + [alfa] for c in _rampa(d["arriendo_ref_millones"], RAMPA_PUNTAJE, 0, 15)]
        sobre = d["arriendo_ref_millones"] > presupuesto
        d.loc[sobre, "color"] = pd.Series([[90, 20, 30, 220]] * int(sobre.sum()), index=d.index[sobre])
        ley = {"tipo": "continua", "colores": RAMPA_PUNTAJE, "etiquetas": ["0", "5", "10", "15+ M/mes"],
               "titulo": "Arriendo de referencia de 80 m² (COP millones/mes)",
               "nota": f"Vino oscuro = supera el presupuesto de COP {presupuesto:g} M."}
    elif capa.startswith("Índice"):
        d["color"] = [c + [alfa] for c in _rampa(d["isu"], RAMPA_SUELO, 15, 95)]
        ley = {"tipo": "continua", "colores": RAMPA_SUELO, "etiquetas": ["15", "35", "55", "75", "95"],
               "titulo": "Índice de sobremesa urbana (0–100, propuesta)"}
    elif capa.startswith("Estabilidad"):
        d["color"] = [c + [alfa] for c in _rampa(d["estabilidad_clase"], RAMPA_CAFES[::-1], 0.4, 1.0)]
        ley = {"tipo": "continua", "colores": RAMPA_CAFES[::-1], "etiquetas": ["≤ 40 %", "70 %", "100 %"],
               "titulo": "Remuestreos en que la zona conserva su clase"}
    elif capa.startswith("Errores"):
        d["color"] = d["error_prueba"].map(lambda e: ERRORES.get(e, [235, 230, 224]) + ([alfa] if e in ERRORES else [60]))
        ley = {"tipo": "categorias", "items": ERRORES}
    else:
        d["color"] = d["segmento"].map(lambda s: SEGMENTOS.get(s, [150, 150, 150]) + [alfa])
        ley = {"tipo": "categorias", "items": SEGMENTOS}
    return d, ley


def vista_en(celda: str, zoom: float = 13.2) -> pdk.ViewState:
    import h3
    la, lo = h3.cell_to_latlng(celda)
    return pdk.ViewState(latitude=la, longitude=lo, zoom=zoom, pitch=0)


def deck(d: pd.DataFrame, tiendas: dict, seleccion: str | None = None, vista=None, zoom: float | None = None,
         extra: pd.DataFrame | None = None) -> pdk.Deck:
    cols = ["h3", "color", "ref", "clase_txt", "puntaje_txt", "cafes_txt", "dist_txt"]
    capa = pdk.Layer(
        "H3HexagonLayer", d[cols], id="zonas", pickable=True, filled=True, extruded=False,
        stroked=True, get_hexagon="h3", get_fill_color="color", get_line_color=[255, 255, 255, 90],
        line_width_min_pixels=0.3, auto_highlight=True, highlight_color=[36, 28, 24, 90],
    )
    capas = [capa]
    if seleccion:
        capas.append(pdk.Layer("H3HexagonLayer", pd.DataFrame({"h3": [seleccion]}), id="seleccion",
                               filled=True, get_fill_color=[166, 58, 69, 70], stroked=True, get_hexagon="h3",
                               get_line_color=[166, 58, 69, 255], line_width_min_pixels=4, pickable=False))
    # deck.gl solo trae glifos ASCII por defecto; se quitan tildes de las etiquetas del mapa
    if extra is not None and len(extra):
        capas.append(pdk.Layer("H3HexagonLayer", extra[["h3"]], id="plan", filled=True, get_fill_color=[166, 58, 69, 200],
                               stroked=True, get_line_color=[36, 28, 24, 255], line_width_min_pixels=3, pickable=False))
    t = pd.DataFrame([{"nombre": _ascii(k), "lat": v[0], "lon": v[1]} for k, v in tiendas.items()])
    capas += [
        pdk.Layer("ScatterplotLayer", t, id="tiendas", get_position=["lon", "lat"], get_radius=170,
                  radius_min_pixels=6, get_fill_color=[36, 28, 24, 255], get_line_color=[255, 255, 255, 255],
                  stroked=True, line_width_min_pixels=2, pickable=False),
        pdk.Layer("TextLayer", t, id="tiendas_txt", get_position=["lon", "lat"], get_text="nombre",
                  get_size=13, get_color=[36, 28, 24, 255], get_pixel_offset=[0, -18],
                  background=True, get_background_color=[247, 244, 239, 230], font_weight=700),
    ]
    vista = vista or pdk.ViewState(latitude=config.CENTRO_MAPA["lat"], longitude=config.CENTRO_MAPA["lon"],
                                   zoom=zoom or config.CENTRO_MAPA["zoom"], pitch=0)
    return pdk.Deck(
        layers=capas, initial_view_state=vista, map_style=pdk.map_styles.CARTO_LIGHT, map_provider="carto",
        tooltip={"html": "<b>{ref}</b><br/>{clase_txt}<br/>Puntaje: {puntaje_txt}<br/>{cafes_txt}<br/>{dist_txt}",
                 "style": {"backgroundColor": "#241C18", "color": "#F7F4EF", "fontSize": "12px"}},
    )


def preparar_tooltip(d: pd.DataFrame) -> pd.DataFrame:
    from .logic import referencia
    d = d.copy()
    d["ref"] = [referencia(r) for _, r in d.iterrows()]
    d["clase_txt"] = d["clase"].map(lambda c: f"{CLASES[c]['simbolo']} {c}")
    d["puntaje_txt"] = (d["puntaje"] * 100).round(0).astype(int).astype(str) + " %"
    d["cafes_txt"] = "Cafés: " + d["n_cafes"].astype(str) + " · esperados " + d["cafes_esperados"].round(1).astype(str)
    d["dist_txt"] = ("Sobremesa urbana: " + d["isu"].round(0).astype(int).astype(str) + "/100<br/>Tienda más cercana: "
                     + d["tienda_cercana"] + " (" + (d["dist_min_m"] / 1000).round(1).astype(str) + " km)")
    return d
