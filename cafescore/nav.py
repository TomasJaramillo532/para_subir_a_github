"""Registro de páginas para enlaces internos (st.page_link) sin rutas de archivo."""
import streamlit as st

PAGINAS: dict = {}


def enlace(clave: str, etiqueta: str, icono: str | None = None):
    p = PAGINAS.get(clave)
    if p is not None:
        st.page_link(p, label=etiqueta, icon=icono, width="stretch")
