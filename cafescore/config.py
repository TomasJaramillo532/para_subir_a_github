"""Constantes de presentación y rutas. Sin lógica de modelo."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# Artefactos de la interfaz (escritos por pipeline/build_artifacts.py) junto a los de la zona fija en model/
RUTA_ZONAS = RAIZ / "model" / "zonas.csv.gz"
RUTA_METRICAS = RAIZ / "model" / "metricas.json"
RUTA_METADATA = RAIZ / "model" / "app.json"
RUTA_MODELO = RAIZ / "model" / "pipeline.joblib"      # exportado con exportar.py (zona fija)
RUTA_FICHA = RAIZ / "docs" / "ficha_modelo.md"

NOMBRE = "CAFÉSCORE"
LEMA = "Intelligence for Location Decisions"
SUBTITULO = "Inteligencia geoespacial para la expansión estratégica de Cereza Café"

# Paleta de marca (ajustada para contraste AA sobre marfil/blanco)
ESPRESSO = "#241C18"
TOSTADO = "#5B4033"
MARFIL = "#F7F4EF"
OLIVA = "#657B62"
CEREZA = "#A63A45"
GRIS = "#6B6B6B"  # más oscuro que #737373 para contraste 4.5:1 sobre marfil

# Clases: color + símbolo + texto (nunca solo color)
CLASES = {
    "Oportunidad": {"color": "#2E7D4F", "rgb": [46, 125, 79], "simbolo": "▲", "badge": "green",
                     "corta": "Perfil de demanda con menos cafés de los esperados"},
    "En equilibrio": {"color": "#3D6FA8", "rgb": [61, 111, 168], "simbolo": "●", "badge": "blue",
                       "corta": "Perfil de demanda y oferta cercana a lo esperado"},
    "Saturada": {"color": "#C8553D", "rgb": [200, 85, 61], "simbolo": "■", "badge": "red",
                  "corta": "Más cafés de los que el perfil de la zona sugiere"},
    "Sin demanda": {"color": "#A8A29A", "rgb": [168, 162, 154], "simbolo": "○", "badge": "gray",
                     "corta": "El perfil no se parece al de las zonas con café"},
}
ORDEN_CLASES = ["Oportunidad", "En equilibrio", "Saturada", "Sin demanda"]

TIENDA_COLOR = [36, 28, 24]

# Límites de Bogotá urbana para validar coordenadas (amplios, solo para detectar errores)
LAT_MIN, LAT_MAX = 4.40, 4.85
LON_MIN, LON_MAX = -74.25, -73.98

CENTRO_MAPA = {"lat": 4.632, "lon": -74.105, "zoom": 10.25}
