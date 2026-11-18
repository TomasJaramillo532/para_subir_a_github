"""Componentes visuales reutilizables. CSS mínimo y aislado para no depender de clases internas de Streamlit."""
from __future__ import annotations

import html

import streamlit as st

from . import config
from .config import CLASES, ORDEN_CLASES

CSS = f"""
<style>
.cs-eyebrow {{font-size:.78rem; letter-spacing:.14em; text-transform:uppercase; color:{config.CEREZA}; font-weight:700; margin-bottom:.1rem}}
.cs-title {{font-size:1.9rem; font-weight:750; color:{config.ESPRESSO}; line-height:1.15; margin:0}}
.cs-sub {{color:{config.GRIS}; font-size:1rem; margin:.25rem 0 .6rem 0}}
.cs-legend {{display:flex; flex-wrap:wrap; gap:.5rem 1.1rem; align-items:center; font-size:.86rem; color:{config.ESPRESSO}}}
.cs-legend .sw {{display:inline-block; width:.95rem; height:.95rem; border-radius:3px; margin-right:.35rem; vertical-align:-2px; border:1px solid rgba(0,0,0,.15)}}
.cs-ramp {{height:.7rem; border-radius:4px; border:1px solid rgba(0,0,0,.12)}}
.cs-ramp-lab {{display:flex; justify-content:space-between; font-size:.78rem; color:{config.GRIS}}}
.cs-note {{border-left:3px solid {config.TOSTADO}; padding:.45rem .8rem; background:rgba(91,64,51,.06); border-radius:4px; font-size:.88rem; color:{config.ESPRESSO}}}
.cs-pending {{border:1px dashed {config.TOSTADO}; padding:.9rem 1rem; border-radius:8px; background:#FFFDF9}}
.cs-foot {{font-size:.78rem; color:{config.GRIS}; border-top:1px solid #E4DED6; margin-top:1.6rem; padding-top:.6rem}}
.cs-stats {{display:grid; grid-template-columns:repeat(auto-fit,minmax(78px,1fr)); gap:.5rem; margin:.5rem 0}}
.cs-stat {{background:#FFFFFF; border:1px solid #E4DED6; border-radius:8px; padding:.45rem .55rem}}
.cs-stat .l {{font-size:.74rem; color:{config.GRIS}; white-space:nowrap}}
.cs-stat .v {{font-size:1.3rem; font-weight:700; color:{config.ESPRESSO}}}
.cs-kv {{font-size:.9rem; line-height:1.55}}
.cs-kv b {{color:{config.ESPRESSO}}}
</style>
"""


def estilos():
    st.markdown(CSS, unsafe_allow_html=True)


def encabezado(eyebrow: str, titulo: str, subtitulo: str = ""):
    st.markdown(
        f'<div class="cs-eyebrow">{html.escape(eyebrow)}</div>'
        f'<h1 class="cs-title">{html.escape(titulo)}</h1>'
        + (f'<p class="cs-sub">{html.escape(subtitulo)}</p>' if subtitulo else ""),
        unsafe_allow_html=True,
    )


def badge_clase(clase: str):
    c = CLASES.get(clase)
    if c:
        st.badge(f"{c['simbolo']} {clase}", color=c["badge"])


def texto_clase(clase: str) -> str:
    c = CLASES.get(clase, {})
    return f"{c.get('simbolo', '')} {clase}".strip()


def leyenda_clases(conteos: dict | None = None):
    items = []
    for k in ORDEN_CLASES:
        c = CLASES[k]
        n = f" · {conteos.get(k, 0):,}".replace(",", ".") if conteos else ""  # solo un entero
        items.append(f'<span title="{html.escape(c["corta"])}"><span class="sw" style="background:{c["color"]}"></span>'
                     f'{c["simbolo"]} <b>{k}</b>{n}</span>')
    items.append('<span><span class="sw" style="background:#241C18;border-radius:50%"></span>★ Tienda Cereza</span>')
    st.markdown(f'<div class="cs-legend" role="list" aria-label="Leyenda de clases">{"".join(items)}</div>',
                unsafe_allow_html=True)


def leyenda_continua(titulo: str, colores: list[str], etiquetas: list[str], nota: str = ""):
    grad = ", ".join(colores)
    st.markdown(
        f'<div style="font-size:.85rem;font-weight:600;margin-bottom:.2rem">{html.escape(titulo)}</div>'
        f'<div class="cs-ramp" style="background:linear-gradient(90deg,{grad})" role="img" aria-label="{html.escape(titulo)}"></div>'
        f'<div class="cs-ramp-lab">{"".join(f"<span>{html.escape(e)}</span>" for e in etiquetas)}</div>'
        + (f'<div style="font-size:.78rem;color:{config.GRIS};margin-top:.2rem">{html.escape(nota)}</div>' if nota else ""),
        unsafe_allow_html=True,
    )


def nota(texto: str):
    st.markdown(f'<div class="cs-note">{texto}</div>', unsafe_allow_html=True)


def pendiente(titulo: str, cuerpo: str):
    st.markdown(f'<div class="cs-pending"><b>⏳ {html.escape(titulo)}</b><br>{cuerpo}</div>', unsafe_allow_html=True)


def pie():
    st.markdown(
        '<div class="cs-foot">Datos: © colaboradores de OpenStreetMap (ODbL) · Overture Maps (CDLA-Permissive 2.0) · '
        'Foursquare OS Places (Apache 2.0) · Catastro de Bogotá y TransMilenio (datos abiertos) · Mapa base © CARTO. '
        'Cereza Café es una marca ficticia del curso Minería de Datos (Universidad de los Andes). '
        'CaféScore apoya la decisión de qué zonas estudiar; no garantiza la rentabilidad de una tienda ni autoriza inversiones.</div>',
        unsafe_allow_html=True,
    )


def kv(pares: list[tuple[str, str]]):
    filas = "".join(f"<div><span style='color:{config.GRIS}'>{html.escape(k)}</span> · <b>{html.escape(v)}</b></div>" for k, v in pares)
    st.markdown(f'<div class="cs-kv">{filas}</div>', unsafe_allow_html=True)


def stats(items: list[tuple[str, str, str]]):
    """Fila compacta de indicadores (etiqueta, valor, descripción accesible)."""
    cel = "".join(f'<div class="cs-stat" title="{html.escape(t)}"><div class="l">{html.escape(l)}</div>'
                  f'<div class="v">{html.escape(v)}</div></div>' for l, v, t in items)
    st.markdown(f'<div class="cs-stats">{cel}</div>', unsafe_allow_html=True)
