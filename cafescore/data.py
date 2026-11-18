"""Carga de artefactos con caché y comprobación de esquema."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from . import config
import core

COLUMNAS_ZONAS = {"h3", "lat", "lon", "n_cafes", "puntaje", "cafes_esperados", "brecha", "clase",
                  "arriendo_ref_millones", "dist_min_m", "tienda_cercana", "factores_a_favor",
                  "factores_en_contra", "segmento", "particion"}


class ArtefactoFaltante(RuntimeError):
    pass


def estado_artefactos() -> dict:
    rutas = {"Tabla de zonas (model/zonas.csv.gz)": config.RUTA_ZONAS, "Métricas (model/metricas.json)": config.RUTA_METRICAS,
             "Modelo (model/pipeline.joblib)": config.RUTA_MODELO, "Datos de la interfaz (model/app.json)": config.RUTA_METADATA}
    return {k: v.exists() for k, v in rutas.items()}


@st.cache_data(show_spinner="Cargando zonas…")
def zonas() -> pd.DataFrame:
    if not config.RUTA_ZONAS.exists():
        raise ArtefactoFaltante("No se encontró data/zonas.csv.gz. Ejecute pipeline/build_artifacts.py.")
    df = pd.read_csv(config.RUTA_ZONAS)
    faltan = COLUMNAS_ZONAS - set(df.columns)
    if faltan:
        raise ArtefactoFaltante(f"La tabla de zonas no tiene las columnas {sorted(faltan)}")
    if len(df) != 3275 or df["h3"].duplicated().any():
        raise ArtefactoFaltante("La tabla de zonas debe tener 3.275 celdas únicas.")
    df[["factores_a_favor", "factores_en_contra"]] = df[["factores_a_favor", "factores_en_contra"]].fillna("")
    # Razones y decisión calculadas por exportar.py (zona fija) para cada zona
    res = core.cargar_resultados()
    if res is not None and {"h3", "razones", "decision"}.issubset(res.columns):
        df = df.merge(res[["h3", "razones", "decision"]], on="h3", how="left")
    else:
        df["razones"], df["decision"] = "", ""
    df["razones"] = df["razones"].fillna("")
    return df


@st.cache_data
def metricas() -> dict:
    if not config.RUTA_METRICAS.exists():
        raise ArtefactoFaltante("No se encontró data/metricas.json.")
    return json.loads(config.RUTA_METRICAS.read_text(encoding="utf-8"))


@st.cache_data
def metadata() -> dict:
    if not config.RUTA_METADATA.exists():
        raise ArtefactoFaltante("No se encontró model/metadata.json.")
    return json.loads(config.RUTA_METADATA.read_text(encoding="utf-8"))


@st.cache_resource(show_spinner="Cargando modelo…")
def modelo():
    """Metadatos y pipeline de la zona fija (core/)."""
    return core.cargar_metadata(), core.cargar_modelo()


def fila_metodo(m: dict, metodo: str) -> dict | None:
    return next((t for t in m["tabla_prueba"] if t["metodo"] == metodo), None)
