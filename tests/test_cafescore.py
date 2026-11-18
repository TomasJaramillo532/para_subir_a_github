"""Pruebas de integridad, cálculo geográfico, modelo y reglas de negocio.

Ejecutar desde la raíz:  python -m pytest -q
"""
import json
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import pytest

from cafescore import geo, logic
import core

RAIZ = Path(__file__).resolve().parents[1]
Z = pd.read_csv(RAIZ / "model" / "zonas.csv.gz")
M = json.loads((RAIZ / "model" / "metricas.json").read_text(encoding="utf-8"))
MD = json.loads((RAIZ / "model" / "app.json").read_text(encoding="utf-8"))
META = core.cargar_metadata()
MODELO = core.cargar_modelo()
COLS = core.columnas_de_entrada(META)


# ----------------------------------------------------------------- integridad de datos
def test_tabla_completa_y_unica():
    assert len(Z) == 3275 and Z["h3"].is_unique
    assert set(Z["clase"]) <= {"Oportunidad", "En equilibrio", "Saturada", "Sin demanda"}
    assert Z["puntaje"].between(0, 1).all()


def test_no_se_publican_datos_originales():
    prohibidas = {"nombres_cafes", "n_cafes_por_nombre", "fsq_cafes_hist", "gastro_no_cafe_300m"}
    assert not prohibidas & set(Z.columns)
    assert not list(RAIZ.rglob("cafescore_data*.csv"))
    res = core.cargar_resultados()
    assert not prohibidas & set(res.columns)


def test_h3_resolucion_9_y_coordenadas_coherentes():
    assert all(h3.get_resolution(c) == 9 for c in Z["h3"].head(200))
    assert (Z.apply(lambda r: h3.latlng_to_cell(r.lat, r.lon, 9), axis=1) == Z["h3"]).all()


def test_brecha_es_esperados_menos_observados():
    assert np.allclose(Z["brecha"], Z["cafes_esperados"] - Z["n_cafes"], atol=2e-4)


def test_clasificacion_aplica_la_regla_documentada():
    d, u = MD["supuestos"]["clasificacion"]["delta_cafes"], MD["umbral"]

    def regla(p, b):
        if b <= -d:
            return "Saturada"
        if p < u:
            return "Sin demanda"
        return "Oportunidad" if b >= d else "En equilibrio"

    # tolerancia por redondeo a 4 decimales en el archivo
    lejos = (Z["brecha"].abs().sub(d).abs() > 1e-3) & ((Z["puntaje"] - u).abs() > 1e-3)
    esperado = [regla(p, b) for p, b in zip(Z.puntaje, Z.brecha)]
    assert (Z.loc[lejos, "clase"] == pd.Series(esperado, index=Z.index)[lejos]).all()


def test_distancias_haversine_recalculadas():
    for t, (la, lo) in MD["tiendas"].items():
        d = geo.haversine_m(Z.lat.values, Z.lon.values, la, lo)
        assert np.allclose(d, Z[f"dist_{t}"], atol=0.1)
    assert np.allclose(Z[[f"dist_{t}" for t in MD["tiendas"]]].min(axis=1), Z["dist_min_m"], atol=0.1)


def test_arriendo_es_proporcional_al_suelo():
    a = MD["supuestos"]["arriendo"]
    esperado = a["ancla_millones_mes"] * Z["valor_suelo_m2"] / M["arriendo"]["mediana_suelo_ancla"]
    assert np.allclose(esperado, Z["arriendo_ref_millones"], atol=1e-3)


# ----------------------------------------------------------------- métricas
def test_costos_coinciden_con_matriz_de_confusion():
    for t in M["tabla_prueba"]:
        assert t["costo"] == 60 * t["fn"] + 20 * t["fp"]
        assert t["vp"] + t["fn"] + t["fp"] + t["vn"] == M["particion"]["celdas_prueba"]


def test_reproduce_informe_entrega_1():
    assert M["verificacion_e1"] and all(v["coincide"] for v in M["verificacion_e1"])


def test_metricas_de_la_plantilla_coinciden():
    mt = META["metricas"]
    fs = next(t for t in M["tabla_prueba"] if t["metodo"] == M["seleccionado"])
    assert mt["costo_regla"] - mt["costo_modelo"] == -fs["dif_vs_regla"]
    assert np.allclose(mt["intervalo_diferencia"], [-fs["dif_vs_regla_ic95"][1], -fs["dif_vs_regla_ic95"][0]])


def test_seleccion_por_validacion_cruzada_no_por_prueba():
    modelos = [t for t in M["tabla_prueba"] if t["familia"] in ("Modelo base (E1)", "Ensamble (final)")]
    elegido = min(modelos, key=lambda t: t["costo_cv"])
    assert elegido["metodo"] == M["seleccionado"]


def test_validacion_aperturas_no_inventada():
    v = M["validacion_aperturas"]
    assert v["estado"] in ("pendiente", "completa", "error")
    if v["estado"] == "pendiente":
        assert "tasa_oportunidad" not in v


# ----------------------------------------------------------------- modelo
def test_modelo_exportado_reproduce_costo_en_prueba():
    pru = Z[Z["particion"] == "prueba"]
    p = core.predecir_probabilidad(MODELO, META, pru)
    y = (pru["n_cafes"] > 0).astype(int).values
    pred = (np.array(core.decidir(p, META)) == META["decisiones"][1]).astype(int)
    costo = 60 * int(((y == 1) & (pred == 0)).sum()) + 20 * int(((y == 0) & (pred == 1)).sum())
    fila = next(t for t in M["tabla_prueba"] if t["metodo"] == M["seleccionado"])
    assert costo == fila["costo"] == META["metricas"]["costo_modelo"]


def test_zona_fija_valida_y_explica():
    X = Z[COLS].head(3).copy()
    _, errores, _ = core.validar(X.drop(columns=COLS[0]), META)
    assert errores
    Xm = X.copy().astype(object); Xm.iloc[0, 1] = "abc"
    _, errores, _ = core.validar(Xm, META)
    assert errores
    datos, errores, _ = core.validar(X, META)
    assert not errores
    r = core.evaluar(MODELO, META, datos)
    assert all(0 <= x["probabilidad"] <= 1 and x["decision"] in META["decisiones"] for x in r)


def test_resultados_de_exportar_coinciden_con_el_mapa():
    res = core.cargar_resultados()
    m = res.merge(Z[["h3", "puntaje", "clase"]], on="h3", suffixes=("", "_z"))
    assert len(m) == 3275 and np.allclose(m["probabilidad"], m["puntaje"], atol=1e-3)
    assert (m["clase"] == m["clase_z"]).all()
    lejos = (m["probabilidad"] - META["umbrales"][0]).abs() > 1e-4  # resultados.csv redondea a 4 decimales
    assert ((m["probabilidad"] >= META["umbrales"][0]) == (m["decision"] == "Estudiar la zona"))[lejos].all()


# ----------------------------------------------------------------- geografía
def test_haversine_un_grado_de_latitud():
    assert abs(geo.haversine_m(0, 0, 1, 0) - 111_195.08) < 1


def test_localizar_tiendas_y_errores():
    validas = set(Z["h3"])
    for la, lo in MD["tiendas"].values():
        r = geo.localizar(la, lo, validas)
        assert r.estado == "ok" and r.h3 == h3.latlng_to_cell(la, lo, 9)
    assert geo.localizar("abc", -74, validas).estado == "invalida"
    assert geo.localizar(95, -74, validas).estado == "invalida"
    assert geo.localizar(40.0, -74.0, validas).estado == "fuera_bogota"
    assert geo.localizar(-74.06, 4.64, validas).estado == "fuera_bogota"
    assert geo.localizar(4.6060, -74.0420, validas).estado == "fuera_area"  # cerros orientales


# ----------------------------------------------------------------- ranking
def test_ranking_respeta_filtros_y_separacion():
    f = logic.filtrar(Z, 12, ["Oportunidad"], (0, 1), (1000, 1e9), None, True)
    assert (f["clase"] == "Oportunidad").all() and (f["arriendo_ref_millones"] <= 12).all() and (f["dist_min_m"] >= 1000).all()
    r = logic.rankear(f, 10, 600)
    assert len(r) == 10 and list(r["posicion"]) == list(range(1, 11))
    for i in range(len(r)):
        for j in range(i + 1, len(r)):
            assert geo.haversine_m(r.lat.iloc[i], r.lon.iloc[i], r.lat.iloc[j], r.lon.iloc[j]) >= 600
    assert r["brecha"].is_monotonic_decreasing


def test_formato_colombiano():
    assert logic.fmt_num(1234567.8, 1) == "1.234.567,8"
    assert logic.fmt_cop(-260) == "COP -260 M"


# ----------------------------------------------------------------- v2
from cafescore import reports, sim  # noqa: E402


def test_simulador_reproduce_tabla_oficial():
    s = M["simulador"]
    r = sim.simular(s, 60, 20, sim.matriz_bootstrap(s["bloques"]))
    fs = next(t for t in M["tabla_prueba"] if t["metodo"] == M["seleccionado"])
    fr = next(t for t in M["tabla_prueba"] if t["metodo"] == "Regla simple")
    assert r["modelo"]["costo"] == fs["costo"] and r["regla"]["costo"] == fr["costo"]
    assert np.allclose(r["dif_ic"], fs["dif_vs_regla_ic95"]) and np.allclose(r["modelo"]["ic"], fs["ic95"])
    assert r["umbral"] == MD["umbral"]


def test_incertidumbre_valida():
    assert Z["estabilidad_clase"].between(0, 1).all() and (Z["puntaje_p05"] <= Z["puntaje_p95"]).all()
    assert Z["isu"].between(0, 100).all()
    assert (Z.loc[Z.particion == "entrenamiento", "error_prueba"].fillna("") == "").all()


def test_riesgo_y_binomial():
    f = Z[Z.clase == "Oportunidad"].iloc[0].copy()
    f["dist_min_m"], f["arriendo_ref_millones"], f["n_cafes"] = 5000, 3, 1
    f["estabilidad_clase"], f["puntaje_p05"], f["puntaje_p95"] = 1.0, 0.7, 0.8
    assert logic.riesgo(f, 12, 1000)[0] == "Bajo"
    f["arriendo_ref_millones"], f["dist_min_m"], f["estabilidad_clase"] = 13, 200, 0.5
    assert logic.riesgo(f, 12, 1000)[0] == "Alto"
    assert abs(logic.binom_al_menos(2, 2, 0.5) - 0.25) < 1e-12
    assert logic.estudios_necesarios(0.375) == 7


def test_documentos_descargables():
    r = logic.rankear(logic.filtrar(Z, 12, ["Oportunidad"], (0, 1), (1000, 1e9), None, True), 10, 600)
    h = reports.memo(r, M, MD, 12, 1000, 158, 130, 50.0)
    assert h.startswith("<!DOCTYPE html>") and "Recomendación" in h and "OpenStreetMap" in h
    assert "Lista de verificación" in reports.ficha(r.iloc[0], MD, 12, 1000)
