"""Documentos descargables (HTML imprimible a PDF desde el navegador): memo y ficha de zona."""
from __future__ import annotations

import html
from datetime import date

import pandas as pd

from . import logic

ESTILO = """
<style>
@page { size: A4; margin: 16mm; }
body { font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; color:#241C18; font-size:11pt; line-height:1.45; max-width:780px; margin:24px auto; }
h1 { font-size:18pt; margin:0 0 2px 0; } h2 { font-size:12pt; color:#A63A45; margin:14px 0 4px 0; text-transform:uppercase; letter-spacing:.06em; }
.meta { color:#6B6B6B; font-size:9.5pt; margin-bottom:10px; border-bottom:2px solid #A63A45; padding-bottom:6px; }
table { border-collapse:collapse; width:100%; font-size:9.5pt; } th, td { border-bottom:1px solid #E4DED6; padding:4px 6px; text-align:left; }
th { background:#F7F4EF; } .nota { font-size:9pt; color:#6B6B6B; } .caja { background:#F7F4EF; border-left:3px solid #5B4033; padding:6px 10px; }
</style>
"""


def _e(x) -> str:
    return html.escape(str(x))


def memo(r: pd.DataFrame, m: dict, md: dict, presupuesto: float, radio: float, n_op: int, n_filtro: int, isu_ciudad: float) -> str:
    sel = m["seleccionado"]
    fs = next(t for t in m["tabla_prueba"] if t["metodo"] == sel)
    lo, hi = fs["dif_vs_regla_ic95"]
    val = m["valor"]
    top = r.head(5)
    filas = "".join(
        f"<tr><td>{int(f['posicion'])}</td><td>{_e(logic.referencia(f))}</td><td>{f['puntaje'] * 100:.0f} %</td>"
        f"<td>{int(f['n_cafes'])} / {logic.fmt_num(f['cafes_esperados'], 1)}</td><td>{f['isu']:.0f}</td>"
        f"<td>{logic.fmt_num(f['arriendo_ref_millones'], 1)}</td><td>{logic.fmt_m(f['dist_min_m'])} m ({_e(f['tienda_cercana'])})</td>"
        f"<td>{logic.riesgo(f, presupuesto, radio)[0]}</td></tr>" for _, f in top.iterrows())
    isu_top = float(top["isu"].mean()) if len(top) else float("nan")
    estudios = logic.estudios_necesarios(val["precision_modelo"])
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Memo CaféScore</title>{ESTILO}</head><body>
<h1>Memo para la fundadora · ¿Dónde buscar local en 2027?</h1>
<div class="meta">CaféScore · Cereza Café · {date.today().isoformat()} · Modelo: {_e(sel)} · Datos: cafés Overture sept. 2026, suelo Catastro 2026</div>
<h2>Recomendación</h2>
<p>Concentrar los estudios de campo en zonas de <b>alta sobremesa urbana</b>: lugares con oficinas, universidades y espacios donde la
gente se queda, y que hoy tienen menos cafés de los que su perfil sugiere. Las cinco primeras zonas tienen un índice de sobremesa
promedio de <b>{isu_top:.0f}</b> sobre 100, frente a <b>{isu_ciudad:.0f}</b> en la ciudad. De {n_op} zonas de oportunidad,
{n_filtro} cumplen el presupuesto de arriendo de COP {presupuesto:g} M (supuesto) y quedan a más de {logic.fmt_m(radio)} m de las tiendas actuales.</p>
<table><tr><th>#</th><th>Zona</th><th>Puntaje</th><th>Cafés hoy / esperados</th><th>Sobremesa</th><th>Arriendo ref. (M/mes)</th><th>Tienda más cercana</th><th>Riesgo</th></tr>{filas}</table>
<h2>Cuánto vale frente a la regla simple</h2>
<p>En 732 zonas de prueba, el modelo comete errores por COP {logic.fmt_m(fs['costo'])} M frente a COP {logic.fmt_m(fs['costo'] - fs['dif_vs_regla'])} M
de la regla (comercio ≥ 53 negocios y suelo ≥ COP 2,3 M/m²). La diferencia ({logic.fmt_num(fs['dif_vs_regla'], signo=True)} M, IC 95 %
{logic.fmt_num(lo, signo=True)} a {logic.fmt_num(hi, signo=True)}) <b>no es concluyente</b>: la regla bastaría para preseleccionar.
El mapa aporta el orden de prioridad, las razones y la detección de zonas saturadas. Para encontrar 2 zonas aptas se esperan
{logic.fmt_num(val['estudios_modelo'], 1)} estudios con el modelo y {logic.fmt_num(val['estudios_regla'], 1)} con la regla (ahorro esperado {logic.fmt_cop(val['ahorro_vs_regla'], 1)}, no significativo).
Para tener 80 % de probabilidad de encontrar 2 zonas aptas conviene presupuestar unos {estudios} estudios (COP {logic.fmt_m((estudios or 0) * 20)} M).</p>
<h2>Riesgos</h2>
<ul><li>“Apta” significa que la zona tiene el perfil de las que sostienen cafés; no garantiza ventas ni rentabilidad.</li>
<li>Puede haber cafés no registrados y zonas sin uso comercial permitido.</li>
<li>El arriendo es una referencia proporcional al valor del suelo, no un arriendo observado.</li>
<li>La validación con las aperturas de abril–septiembre de 2026 está pendiente.</li></ul>
<h2>Qué falta para usarla</h2>
<p>Validar con el equipo los supuestos de clases, arriendo y radio; recibir el archivo de aperturas; y hacer los estudios de campo:
locales disponibles, arriendo real, uso del suelo, flujo peatonal y competencia.</p>
<p class="nota">El índice de sobremesa urbana es una propuesta operativa (promedio de percentiles de oficinas, universidades y espacios de
permanencia a 300 m) pendiente de validación. Herramienta de apoyo a la decisión; no autoriza inversiones. © colaboradores de OpenStreetMap.</p>
</body></html>"""


def ficha(f: pd.Series, md: dict, presupuesto: float, radio: float) -> str:
    et = md["etiquetas"]
    nivel, pts, motivos = logic.riesgo(f, presupuesto, radio)
    esc = logic.escenario(f["arriendo_ref_millones"])
    dist = "".join(f"<tr><td>{_e(t)}</td><td>{logic.fmt_m(f[f'dist_{t}'])} m</td></tr>" for t in logic.TIENDAS_DEF)
    razones = "<br>".join(_e(logic.razon_negocio(r)) for r in logic.razones_lista(f)) or "—"
    meses = f"{esc['meses_recuperacion']:.0f} meses" if esc["meses_recuperacion"] else "no se recupera con este arriendo"
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Ficha {f['h3']}</title>{ESTILO}</head><body>
<h1>Ficha de zona para estudio de campo</h1>
<div class="meta">{_e(logic.referencia(f))} · H3 {f['h3']} · centro {f['lat']:.5f}, {f['lon']:.5f} · {_e(f['segmento'])} · {date.today().isoformat()}</div>
<h2>Diagnóstico</h2>
<table><tr><th>Clase</th><td>{_e(f['clase'])} (estable en {f['estabilidad_clase'] * 100:.0f} % de los remuestreos)</td></tr>
<tr><th>Puntaje</th><td>{f['puntaje'] * 100:.0f} % (intervalo 90 %: {f['puntaje_p05'] * 100:.0f}–{f['puntaje_p95'] * 100:.0f} %)</td></tr>
<tr><th>Cafés registrados / esperados</th><td>{int(f['n_cafes'])} / {logic.fmt_num(f['cafes_esperados'], 1)} (intervalo {logic.fmt_num(f['esperados_p05'], 1)}–{logic.fmt_num(f['esperados_p95'], 1)})</td></tr>
<tr><th>Índice de sobremesa urbana</th><td>{f['isu']:.0f} / 100 (propuesta)</td></tr>
<tr><th>Razones principales</th><td>{razones}</td></tr>
<tr><th>Riesgo de la recomendación</th><td><b>{nivel}</b> ({pts} puntos): {_e('; '.join(motivos) or 'sin alertas')}</td></tr></table>
<h2>Costo y proximidad</h2>
<table><tr><th>Valor del suelo</th><td>COP {logic.fmt_m(f['valor_suelo_m2'])} por m² (Catastro 2026)</td></tr>
<tr><th>Arriendo de referencia 80 m²</th><td>{logic.fmt_cop(f['arriendo_ref_millones'], 1)}/mes (supuesto, no observado)</td></tr>
<tr><th>Escenario con supuestos del brief</th><td>Margen 15 M − arriendo = {logic.fmt_cop(esc['margen_neto'], 1)}/mes; adecuación de 250 M: {meses}</td></tr>
{dist}</table><p class="nota">Distancias en línea recta (Haversine) desde el centro de la celda; no son distancias de conducción.</p>
<h2>Lista de verificación en campo</h2>
<ul><li>Locales disponibles de ~80 m² y arriendo real pedido.</li><li>Uso del suelo comercial permitido (POT) y licencias.</li>
<li>Conteo de flujo peatonal en mañana, mediodía y tarde.</li><li>Cafés y panaderías no registrados; cadenas presentes.</li>
<li>Público: oficinas, estudiantes, residentes; espacios para quedarse (sobremesa).</li><li>Acceso para abastecimiento desde la tostadora.</li></ul>
<p class="nota">El puntaje describe el perfil de la zona; no es la probabilidad de éxito de una tienda. CaféScore · © colaboradores de OpenStreetMap.</p>
</body></html>"""
