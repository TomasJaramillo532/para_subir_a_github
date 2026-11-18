"""Cálculos geográficos: distancias de gran círculo y localización de celdas H3."""
from __future__ import annotations

from dataclasses import dataclass

import h3
import numpy as np

from . import config

RADIO_TIERRA_M = 6_371_008.8  # radio medio (IUGG)
RESOLUCION_H3 = 9


def haversine_m(lat1, lon1, lat2, lon2):
    """Distancia en línea recta sobre la superficie terrestre, en metros.

    Método Haversine con radio medio. Error < 0,5 % frente al elipsoide WGS84 a esta
    escala. No es distancia de conducción ni de caminata."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_M * np.arcsin(np.sqrt(a))


@dataclass
class ResultadoUbicacion:
    estado: str  # "ok" | "invalida" | "fuera_bogota" | "fuera_area"
    mensaje: str
    h3: str | None = None


def validar_coordenadas(lat, lon) -> tuple[bool, str]:
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False, "Las coordenadas deben ser números (use punto decimal, por ejemplo 4.6486)."
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or np.isnan(lat) or np.isnan(lon):
        return False, "Coordenadas inválidas: la latitud va de −90 a 90 y la longitud de −180 a 180."
    return True, ""


def localizar(lat, lon, celdas_validas: set[str]) -> ResultadoUbicacion:
    """Devuelve la celda H3 (resolución 9) que contiene el punto, si está en el área analizada."""
    ok, msg = validar_coordenadas(lat, lon)
    if not ok:
        return ResultadoUbicacion("invalida", msg)
    lat, lon = float(lat), float(lon)
    if not (config.LAT_MIN <= lat <= config.LAT_MAX and config.LON_MIN <= lon <= config.LON_MAX):
        pista = " ¿Invirtió latitud y longitud?" if (config.LAT_MIN <= lon <= config.LAT_MAX) else ""
        pista = pista or (" En Bogotá la longitud es negativa (oeste)." if lon > 0 else "")
        return ResultadoUbicacion("fuera_bogota", "El punto está fuera de Bogotá." + pista)
    celda = h3.latlng_to_cell(lat, lon, RESOLUCION_H3)
    if celda not in celdas_validas:
        return ResultadoUbicacion(
            "fuera_area",
            "El punto está en Bogotá, pero fuera de las 3.275 zonas urbanas analizadas "
            "(por ejemplo, cerros, grandes parques o zonas sin manzanas catastrales).",
            celda,
        )
    return ResultadoUbicacion("ok", "", celda)


def contorno(celda: str) -> list[list[float]]:
    """Polígono de la celda como [[lon, lat], ...] para pydeck."""
    return [[lng, lat] for lat, lng in h3.cell_to_boundary(celda)]
