"""
CaféScore · Generación de artefactos para la aplicación
=======================================================

Este script NO se ejecuta en Streamlit Cloud. Se corre una sola vez, en local o en
Colab, con el archivo original del curso (que NO se publica en el repositorio):

    python pipeline/build_artifacts.py --datos /ruta/a/cafescore_data.csv \
        [--aperturas /ruta/a/aperturas.csv]

Qué hace:
1. Reproduce exactamente la metodología del cuaderno de la Entrega 1 (semilla 2559,
   partición por bloques, regla simple, logística, árbol, ensambles, umbrales por costo).
2. Verifica que las cifras de prueba coincidan con las reportadas en el informe.
   Si no coinciden, se detiene: la app no debe mostrar cifras distintas al informe.
3. Calcula los puntajes del mapa con predicciones fuera de bloque (validación cruzada
   por bloques sobre las 3.275 celdas): ninguna celda se puntúa con un modelo que vio su bloque.
4. Entrena el modelo de conteo (misma partición), calcula la brecha y la clasificación
   según la propuesta v1 (parámetros en SUPUESTOS, marcados como pendientes de validación).
5. Exporta: model/cafescore_modelo.joblib, model/metadata.json, data/zonas.csv.gz,
   data/metricas.json. Ningún archivo exportado contiene nombres de negocios.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import warnings
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import KMeans
from sklearn.ensemble import (GradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier)
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

RAIZ = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------------------
# Constantes del cuaderno (Entrega 1) — NO cambiar: garantizan reproducibilidad
# --------------------------------------------------------------------------------------
SEMILLA = 2559
COSTO_FN = 60
COSTO_FP = 20
PROP_PRUEBA = 0.20
K_PLIEGUES = 5
N_BOOTSTRAP = 1000
UMBRALES = np.round(np.arange(0.05, 0.96, 0.01), 2)
COSTO_ESTUDIO = 20  # millones por zona estudiada (brief)

TIENDAS = {
    "Chapinero": (4.6486, -74.0628),
    "Teusaquillo": (4.6318, -74.0726),
    "Usaquén": (4.6950, -74.0306),
}

# Cifras de prueba reportadas en el informe de la Entrega 1 (para verificar reproducción)
REPORTADO_E1 = {
    "Estudiarlas todas": 11820,
    "No estudiar ninguna": 8460,
    "Regla TransMilenio (< 500 m)": 7400,
    "Regla simple": 6140,
    "Árbol de decisión": 6080,
    "Regresión logística": 5880,
}

# --------------------------------------------------------------------------------------
# SUPUESTOS DE DESPLIEGUE — propuesta v1, PENDIENTES DE VALIDACIÓN DEL EQUIPO
# Se exportan a metadata.json; la app los muestra como supuestos, no como datos.
# --------------------------------------------------------------------------------------
SUPUESTOS = {
    "version": "v1-propuesta",
    "estado": "pendiente de validación del equipo",
    "clasificacion": {
        "delta_cafes": 1.0,
        "descripcion": (
            "Saturada: hay al menos 1 café más de los que el modelo de conteo espera "
            "(brecha <= -1). Sin demanda: el clasificador no la manda a estudiar "
            "(probabilidad fuera de bloque < umbral del modelo). Oportunidad: la manda a "
            "estudiar y faltan al menos 1 café frente a lo esperado (brecha >= +1). "
            "En equilibrio: el resto (la manda a estudiar y la oferta está a menos de 1 café "
            "de lo esperado)."
        ),
        "orden": ["Saturada", "Sin demanda", "Oportunidad", "En equilibrio"],
    },
    "arriendo": {
        "presupuesto_max_millones": 12.0,
        "area_m2": 80,
        "ancla_millones_mes": 6.5,
        "ancla_fuente": "Fincaraíz (2026), 127 locales en Chapinero Central, promedio 80 m² (citado en el brief)",
        "ancla_centro": TIENDAS["Chapinero"],
        "ancla_radio_m": 800,
        "descripcion": (
            "Arriendo de referencia = 6,5 M × (valor del suelo de la celda / mediana del valor "
            "del suelo de las celdas a 800 m de la tienda de Chapinero). Supone que el arriendo "
            "de un local de 80 m² es proporcional al valor del suelo, anclado en el único dato "
            "observado de arriendos del brief. No es un arriendo observado por zona."
        ),
    },
    "canibalizacion": {
        "radio_m": 1000,
        "descripcion": (
            "Una zona a menos de 1.000 m en línea recta (Haversine) de una tienda actual se "
            "marca con posible canibalización. La distancia no demuestra canibalización por sí sola."
        ),
    },
    "ranking": {
        "descripcion": (
            "Top 10: zonas Oportunidad con arriendo de referencia <= 12 M y a más del radio de "
            "canibalización, ordenadas por brecha (cafés que faltan) y luego por puntaje. Para no "
            "recomendar celdas pegadas, se exige al menos 600 m entre zonas del ranking."
        ),
        "separacion_min_m": 600,
    },
}

ETIQUETAS = {
    "n_manzanas": "manzanas catastrales en la celda",
    "valor_suelo_m2": "valor del suelo",
    "ov_servicios_empresas_300m": "servicios a empresas cerca",
    "ov_comercio_300m": "comercio cerca",
    "ov_educacion_300m": "negocios de educación cerca",
    "ov_salud_300m": "negocios de salud cerca",
    "ov_belleza_estilo_300m": "belleza y estilo cerca",
    "ov_hoteles_300m": "hoteles cerca",
    "ov_entretenimiento_300m": "entretenimiento cerca",
    "ov_deporte_300m": "negocios de deporte cerca",
    "fsq_negocios_hist_300m": "actividad comercial histórica",
    "fsq_oficinas_hist_300m": "oficinas (histórico Foursquare)",
    "osm_universidades_300m": "universidades cerca",
    "osm_colegios_300m": "colegios cerca",
    "osm_oficinas_osm_300m": "oficinas cerca",
    "osm_bancos_300m": "bancos cerca",
    "osm_centros_comerciales_300m": "centros comerciales cerca",
    "osm_parques_300m": "parques cerca",
    "osm_paraderos_sitp_300m": "paraderos SITP cerca",
    "osm_hospitales_clinicas_300m": "hospitales y clínicas cerca",
    "dist_tm_m": "distancia a TransMilenio",
    "tm_flujo_mes": "flujo de la estación troncal",
    "tm_a_500m": "estación troncal a menos de 500 m",
    "mezcla_oficina_uni": "mezcla de oficinas y universidades",
    "densidad_comercial_total": "densidad comercial total",
    "accesibilidad_transporte": "accesibilidad al transporte",
    "diversidad_usos": "diversidad de usos",
}


# Nombres de negocio para las razones de la zona fija (core/) y la tabla de resultados
ETIQUETAS_NEGOCIO = {
    "n_manzanas": "Manzanas catastrales en la zona", "valor_suelo_m2": "Valor del suelo (COP/m²)",
    "ov_servicios_empresas_300m": "Servicios a empresas a 300 m", "ov_comercio_300m": "Comercios a 300 m",
    "ov_educacion_300m": "Negocios de educación a 300 m", "ov_salud_300m": "Negocios de salud a 300 m",
    "ov_belleza_estilo_300m": "Negocios de belleza y estilo a 300 m", "ov_hoteles_300m": "Hoteles a 300 m",
    "ov_entretenimiento_300m": "Negocios de entretenimiento a 300 m", "ov_deporte_300m": "Negocios de deporte a 300 m",
    "fsq_negocios_hist_300m": "Negocios históricos (Foursquare) a 300 m",
    "fsq_oficinas_hist_300m": "Oficinas históricas (Foursquare) a 300 m", "osm_universidades_300m": "Universidades a 300 m",
    "osm_colegios_300m": "Colegios a 300 m", "osm_oficinas_osm_300m": "Oficinas a 300 m", "osm_bancos_300m": "Bancos a 300 m",
    "osm_centros_comerciales_300m": "Centros comerciales a 300 m", "osm_parques_300m": "Parques a 300 m",
    "osm_paraderos_sitp_300m": "Paraderos del SITP a 300 m", "osm_hospitales_clinicas_300m": "Hospitales y clínicas a 300 m",
    "dist_tm_m": "Distancia a TransMilenio (m)", "tm_flujo_mes": "Validaciones mensuales de la estación troncal",
    "tm_a_500m": "Estación troncal a menos de 500 m (1 = sí)", "mezcla_oficina_uni": "Mezcla de oficinas y universidades",
    "densidad_comercial_total": "Densidad comercial a 300 m", "accesibilidad_transporte": "Accesibilidad al transporte",
    "diversidad_usos": "Diversidad de usos del suelo",
}
ETIQUETAS_RESULTADOS = {
    "h3": "Zona (H3)", "lat": "Latitud", "lon": "Longitud", "clase": "Clasificación",
    "isu": "Índice de sobremesa urbana", "n_cafes": "Cafés registrados", "cafes_esperados": "Cafés esperados",
    "brecha": "Brecha (esperados − observados)", "arriendo_ref_millones": "Arriendo de referencia (COP M/mes, supuesto)",
    "dist_min_m": "Distancia a la tienda más cercana (m)", "tienda_cercana": "Tienda Cereza más cercana",
    "tm_estacion": "Estación troncal más cercana",
}


# --------------------------------------------------------------------------------------
# Funciones del cuaderno (idénticas)
# --------------------------------------------------------------------------------------
def construir_variables(tabla: pd.DataFrame) -> pd.DataFrame:
    tabla = tabla.copy()
    tabla["mezcla_oficina_uni"] = tabla["osm_universidades_300m"] * tabla["osm_oficinas_osm_300m"]
    tabla["densidad_comercial_total"] = (tabla["ov_comercio_300m"] + tabla["ov_servicios_empresas_300m"]
                                         + tabla["ov_entretenimiento_300m"])
    tabla["accesibilidad_transporte"] = tabla["tm_flujo_mes"] / (tabla["dist_tm_m"] + 1)
    tipos = [c for c in tabla.columns if c.startswith("ov_")]
    proporciones = tabla[tipos].div(tabla[tipos].sum(axis=1).replace(0, np.nan), axis=0)
    entropia = -(proporciones * np.log(proporciones.where(proporciones > 0))).sum(axis=1)
    tabla["diversidad_usos"] = entropia.fillna(0)
    return tabla


def costo(y_real, y_pred) -> int:
    y_real, y_pred = np.asarray(y_real), np.asarray(y_pred)
    fn = int(((y_real == 1) & (y_pred == 0)).sum())
    fp = int(((y_real == 0) & (y_pred == 1)).sum())
    return COSTO_FN * fn + COSTO_FP * fp


def mejor_umbral(y_real, prob):
    costos = [costo(y_real, (prob >= u).astype(int)) for u in UMBRALES]
    i = int(np.argmin(costos))
    return float(UMBRALES[i]), int(costos[i]), [int(c) for c in costos]


def probabilidades_oof(crear_modelo, X, y, grupos):
    prob = np.zeros(len(y))
    for ent, val in GroupKFold(n_splits=K_PLIEGUES).split(X, y, grupos):
        modelo = crear_modelo()
        modelo.fit(X.iloc[ent], y.iloc[ent])
        prob[val] = modelo.predict_proba(X.iloc[val])[:, 1]
    return prob


def crear_logistica(C):
    return Pipeline([
        ("log", FunctionTransformer(np.log1p)),
        ("escalar", StandardScaler()),
        ("modelo", LogisticRegression(C=C, max_iter=5000)),
    ])


def crear_arbol(profundidad, hoja):
    return DecisionTreeClassifier(max_depth=profundidad, min_samples_leaf=hoja, random_state=SEMILLA)


def crear_rf(n, prof, hoja):
    return RandomForestClassifier(n_estimators=n, max_depth=prof, min_samples_leaf=hoja,
                                  random_state=SEMILLA, n_jobs=-1)


def crear_gb(n, lr, prof, hoja):
    return GradientBoostingClassifier(n_estimators=n, learning_rate=lr, max_depth=prof,
                                      min_samples_leaf=hoja, random_state=SEMILLA)


def haversine_m(lat1, lon1, lat2, lon2):
    """Distancia del gran círculo en metros (radio medio terrestre 6.371.008,8 m)."""
    r = 6_371_008.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------
def main(ruta_datos: Path, ruta_aperturas: Path | None):
    log = []

    def say(msg):
        print(msg)
        log.append(msg)

    datos = pd.read_csv(ruta_datos, encoding="utf-8-sig")
    assert datos.shape == (3275, 33), f"Forma inesperada: {datos.shape}"
    datos["hay_cafe"] = (datos["n_cafes"] > 0).astype(int)
    datos = construir_variables(datos)

    entrada_original = (["n_manzanas", "valor_suelo_m2"]
                        + [c for c in datos.columns if c.startswith(("ov_", "fsq_negocios", "fsq_oficinas", "osm_"))]
                        + ["dist_tm_m", "tm_flujo_mes", "tm_a_500m"])
    nuevas = ["mezcla_oficina_uni", "densidad_comercial_total", "accesibilidad_transporte", "diversidad_usos"]
    FEATURES = [c for c in entrada_original if c in datos.columns] + nuevas
    assert len(FEATURES) == 27

    # ---------------- Partición por bloques (idéntica al cuaderno) ----------------
    rng = np.random.default_rng(SEMILLA)
    bloques = np.array(sorted(datos["bloque"].unique()))
    bloques_prueba = rng.choice(bloques, size=round(PROP_PRUEBA * len(bloques)), replace=False)
    datos["particion"] = np.where(datos["bloque"].isin(bloques_prueba), "prueba", "entrenamiento")
    ent = datos[datos["particion"] == "entrenamiento"].reset_index(drop=True)
    pru = datos[datos["particion"] == "prueba"].reset_index(drop=True)
    say(f"Partición: {ent.bloque.nunique()} bloques/{len(ent)} celdas entrenamiento; "
        f"{pru.bloque.nunique()} bloques/{len(pru)} celdas prueba")
    X_ent, y_ent, g_ent = ent[FEATURES], ent["hay_cafe"], ent["bloque"]
    X_pru, y_pru = pru[FEATURES], pru["hay_cafe"]
    y_arr = y_pru.values

    # ---------------- Regla simple (cortes en entrenamiento) ----------------
    busqueda = []
    for pa in np.arange(0.10, 0.91, 0.05):
        for pb in np.arange(0.10, 0.91, 0.05):
            cc = ent["ov_comercio_300m"].quantile(pa)
            cs = ent["valor_suelo_m2"].quantile(pb)
            pred = (ent["ov_comercio_300m"] >= cc) & (ent["valor_suelo_m2"] >= cs)
            busqueda.append((costo(y_ent, pred.astype(int)), cc, cs))
    costo_regla_ent, CORTE_COMERCIO, CORTE_SUELO = min(busqueda)
    say(f"Regla simple: comercio >= {CORTE_COMERCIO:.0f} y suelo >= {CORTE_SUELO:,.0f} (costo ent {costo_regla_ent})")

    def regla_simple(t):
        return ((t["ov_comercio_300m"] >= CORTE_COMERCIO) & (t["valor_suelo_m2"] >= CORTE_SUELO)).astype(int).values

    # ---------------- Selección de modelos por CV en entrenamiento ----------------
    cv = []
    oof = {}
    for C in [0.01, 0.1, 1, 10]:
        p = probabilidades_oof(lambda: crear_logistica(C), X_ent, y_ent, g_ent)
        u, c, _ = mejor_umbral(y_ent, p)
        cv.append({"modelo": "Regresión logística", "parametros": f"C={C}", "auc_cv": roc_auc_score(y_ent, p), "umbral": u, "costo_cv": c})
        oof[("lr", C)] = p
    for prof in [2, 3, 4, 5, 6, 8]:
        for hoja in [10, 25, 50]:
            p = probabilidades_oof(lambda: crear_arbol(prof, hoja), X_ent, y_ent, g_ent)
            u, c, _ = mejor_umbral(y_ent, p)
            cv.append({"modelo": "Árbol de decisión", "parametros": f"prof={prof}, hoja={hoja}", "auc_cv": roc_auc_score(y_ent, p), "umbral": u, "costo_cv": c})
            oof[("ar", (prof, hoja))] = p
    for n in [200, 400]:
        for prof in [4, 6, 8, None]:
            for hoja in [10, 25]:
                p = probabilidades_oof(lambda: crear_rf(n, prof, hoja), X_ent, y_ent, g_ent)
                u, c, _ = mejor_umbral(y_ent, p)
                cv.append({"modelo": "Bosque aleatorio", "parametros": f"n={n}, prof={prof}, hoja={hoja}", "auc_cv": roc_auc_score(y_ent, p), "umbral": u, "costo_cv": c})
    for n in [100, 200]:
        for lr in [0.03, 0.05, 0.1]:
            for prof in [2, 3]:
                for hoja in [15, 30]:
                    p = probabilidades_oof(lambda: crear_gb(n, lr, prof, hoja), X_ent, y_ent, g_ent)
                    u, c, _ = mejor_umbral(y_ent, p)
                    cv.append({"modelo": "Gradient boosting", "parametros": f"n={n}, lr={lr}, prof={prof}, hoja={hoja}", "auc_cv": roc_auc_score(y_ent, p), "umbral": u, "costo_cv": c})
    cv = pd.DataFrame(cv)
    cv["auc_cv"] = cv["auc_cv"].round(3)
    mejores = (cv.sort_values(["costo_cv", "auc_cv"], ascending=[True, False])
                 .groupby("modelo", sort=False).head(1).set_index("modelo"))
    say("Mejor por familia (CV):\n" + mejores.to_string())

    def params(modelo):
        return dict(x.split("=") for x in mejores.loc[modelo, "parametros"].split(", "))

    C_EL = float(params("Regresión logística")["C"])
    pa = params("Árbol de decisión"); AR = (int(pa["prof"]), int(pa["hoja"]))
    pr = params("Bosque aleatorio"); RF = (int(pr["n"]), None if pr["prof"] == "None" else int(pr["prof"]), int(pr["hoja"]))
    pg = params("Gradient boosting"); GB = (int(pg["n"]), float(pg["lr"]), int(pg["prof"]), int(pg["hoja"]))
    U = {m: float(mejores.loc[m, "umbral"]) for m in mejores.index}

    seleccionado = mejores["costo_cv"].idxmin()
    say(f"Modelo seleccionado por costo en CV (regla del equipo): {seleccionado}")

    # ---------------- Evaluación en prueba (una sola vez) ----------------
    modelos = {
        "Regresión logística": crear_logistica(C_EL).fit(X_ent, y_ent),
        "Árbol de decisión": crear_arbol(*AR).fit(X_ent, y_ent),
        "Bosque aleatorio": crear_rf(*RF).fit(X_ent, y_ent),
        "Gradient boosting": crear_gb(*GB).fit(X_ent, y_ent),
    }
    probas = {m: mod.predict_proba(X_pru)[:, 1] for m, mod in modelos.items()}
    decisiones = {
        "No estudiar ninguna": np.zeros(len(pru), dtype=int),
        "Estudiarlas todas": np.ones(len(pru), dtype=int),
        "Regla TransMilenio (< 500 m)": (pru["tm_a_500m"] == 1).astype(int).values,
        "Regla simple": regla_simple(pru),
    }
    for m in modelos:
        decisiones[m] = (probas[m] >= U[m]).astype(int)

    rng_boot = np.random.default_rng(SEMILLA)
    bloques_pru = pru["bloque"].unique()
    idx_b = {b: np.where(pru["bloque"] == b)[0] for b in bloques_pru}
    muestras = [np.concatenate([idx_b[b] for b in rng_boot.choice(bloques_pru, size=len(bloques_pru), replace=True)])
                for _ in range(N_BOOTSTRAP)]

    def ic(vals):
        lo, hi = np.percentile(vals, [2.5, 97.5])
        return [float(lo), float(hi)]

    familia = {"No estudiar ninguna": "Trivial", "Estudiarlas todas": "Trivial",
               "Regla TransMilenio (< 500 m)": "Regla", "Regla simple": "Regla",
               "Regresión logística": "Modelo base (E1)", "Árbol de decisión": "Modelo base (E1)",
               "Bosque aleatorio": "Ensamble (final)", "Gradient boosting": "Ensamble (final)"}
    tabla = []
    for nombre, pred in decisiones.items():
        vp = int(((y_arr == 1) & (pred == 1)).sum())
        fn = int(((y_arr == 1) & (pred == 0)).sum())
        fp = int(((y_arr == 0) & (pred == 1)).sum())
        vn = int(((y_arr == 0) & (pred == 0)).sum())
        fila = {
            "metodo": nombre, "familia": familia[nombre],
            "costo": costo(y_arr, pred),
            "ic95": ic([costo(y_arr[s], pred[s]) for s in muestras]),
            "zonas_estudiar": int(pred.sum()), "vp": vp, "fn": fn, "fp": fp, "vn": vn,
            "sensibilidad": vp / max(int(y_arr.sum()), 1),
            "precision": (vp / int(pred.sum())) if pred.sum() else None,
            "auc": float(roc_auc_score(y_arr, probas[nombre])) if nombre in probas else None,
            "umbral": U.get(nombre),
            "parametros": mejores.loc[nombre, "parametros"] if nombre in mejores.index else (
                f"comercio >= {CORTE_COMERCIO:.0f} y suelo >= {CORTE_SUELO:,.0f}" if nombre == "Regla simple" else
                ("tm_a_500m = 1" if "TransMilenio" in nombre else "—")),
            "costo_cv": int(mejores.loc[nombre, "costo_cv"]) if nombre in mejores.index else (
                int(costo_regla_ent) if nombre == "Regla simple" else None),
            "seleccionado": nombre == seleccionado,
        }
        if nombre != "Regla simple":
            difs = [costo(y_arr[s], pred[s]) - costo(y_arr[s], decisiones["Regla simple"][s]) for s in muestras]
            fila["dif_vs_regla"] = fila["costo"] - costo(y_arr, decisiones["Regla simple"])
            fila["dif_vs_regla_ic95"] = ic(difs)
        tabla.append(fila)

    # Verificación contra el informe de la Entrega 1
    verif = []
    for t in tabla:
        if t["metodo"] in REPORTADO_E1:
            verif.append({"metodo": t["metodo"], "reportado": REPORTADO_E1[t["metodo"]], "reproducido": t["costo"],
                          "coincide": REPORTADO_E1[t["metodo"]] == t["costo"]})
    for v in verif:
        say(f"  Verificación E1 · {v['metodo']}: informe {v['reportado']} vs reproducido {v['reproducido']} -> {'OK' if v['coincide'] else 'DIFERENTE'}")
    if not all(v["coincide"] for v in verif):
        sys.exit("ERROR: la reproducción no coincide con el informe de la Entrega 1. No se exportan artefactos.")

    # Curva de costo por umbral (CV en entrenamiento)
    curva = {
        "umbrales": [float(u) for u in UMBRALES],
        "Regresión logística": mejor_umbral(y_ent, oof[("lr", C_EL)])[2],
        "Árbol de decisión": mejor_umbral(y_ent, oof[("ar", AR)])[2],
        "regla_simple_ent": int(costo_regla_ent),
    }

    # ---------------- Explicabilidad (modelo seleccionado, datos de prueba) ----------------
    modelo_sel = modelos[seleccionado]
    assert seleccionado == "Regresión logística", "La explicación lineal asume la logística como seleccionada"
    perm = permutation_importance(modelo_sel, X_pru, y_arr, n_repeats=30, random_state=SEMILLA, scoring="roc_auc")
    imp_perm = (pd.DataFrame({"variable": FEATURES, "importancia": perm.importances_mean, "de": perm.importances_std})
                  .sort_values("importancia", ascending=False))

    log_ = modelo_sel.named_steps["log"]; esc = modelo_sel.named_steps["escalar"]; lr_ = modelo_sel.named_steps["modelo"]
    Z_ent = esc.transform(log_.transform(X_ent))
    base_z = Z_ent.mean(axis=0)
    coef = lr_.coef_[0]

    def contribuciones(X):
        return (esc.transform(log_.transform(X)) - base_z) * coef  # SHAP exacto de un modelo lineal (escala log-odds)

    shap_pru = contribuciones(X_pru)
    try:  # Comprobación con la librería shap si está instalada
        import shap
        expl = shap.LinearExplainer(lr_, shap.maskers.Independent(Z_ent, max_samples=len(Z_ent)))
        sv = expl.shap_values(esc.transform(log_.transform(X_pru)))
        err = float(np.abs(sv - shap_pru).max())
        say(f"SHAP (librería) vs contribución lineal: error máximo {err:.2e}")
        shap_check = err
    except Exception as e:  # pragma: no cover
        shap_check = None
        say(f"SHAP no verificado con la librería: {e}")
    imp_shap = (pd.DataFrame({"variable": FEATURES, "shap_abs_medio": np.abs(shap_pru).mean(axis=0),
                              "coeficiente": coef})
                  .sort_values("shap_abs_medio", ascending=False))
    # muestra para gráfico de abeja (prueba)
    beeswarm = []
    for j, f in enumerate(FEATURES):
        vals = X_pru[f].values
        rk = pd.Series(vals).rank(pct=True).values
        for i in range(len(vals)):
            beeswarm.append((f, float(shap_pru[i, j]), float(rk[i])))

    # ---------------- Puntaje del mapa: OOF por bloques sobre todas las celdas ----------------
    X_all, y_all, g_all = datos[FEATURES], datos["hay_cafe"], datos["bloque"]
    p_oof = probabilidades_oof(lambda: crear_logistica(C_EL), X_all, y_all, g_all)
    datos["puntaje"] = p_oof
    datos["pliegue_oof"] = -1
    for k, (_, val) in enumerate(GroupKFold(n_splits=K_PLIEGUES).split(X_all, y_all, g_all)):
        datos.loc[datos.index[val], "pliegue_oof"] = k
    corr_pru = float(np.corrcoef(datos.loc[datos.particion == "prueba", "puntaje"].values, probas[seleccionado])[0, 1])
    say(f"Puntaje OOF (todas las celdas): AUC {roc_auc_score(y_all, p_oof):.3f}; correlación con el modelo final en prueba {corr_pru:.3f}")

    # ---------------- Modelo de conteo (misma partición) ----------------
    y_ent_n, y_pru_n = ent["n_cafes"], pru["n_cafes"]

    def crear_poisson(alpha):
        return Pipeline([("log", FunctionTransformer(np.log1p)), ("escalar", StandardScaler()),
                         ("modelo", PoissonRegressor(alpha=alpha, max_iter=3000))])

    def crear_hgb(lr, hoja):
        return HistGradientBoostingRegressor(loss="poisson", learning_rate=lr, max_iter=300,
                                             min_samples_leaf=hoja, random_state=SEMILLA)

    def oof_reg(crear, X, y, g):
        pred = np.zeros(len(y))
        for a, b in GroupKFold(n_splits=K_PLIEGUES).split(X, y, g):
            m = crear(); m.fit(X.iloc[a], y.iloc[a]); pred[b] = m.predict(X.iloc[b])
        return np.clip(pred, 1e-6, None)

    cv_n = []
    for a in [0.001, 0.01, 0.1, 1.0]:
        p = oof_reg(lambda: crear_poisson(a), X_ent, y_ent_n, g_ent)
        cv_n.append({"modelo": "Regresión de Poisson", "parametros": f"alpha={a}", "devianza_cv": mean_poisson_deviance(y_ent_n, p), "mae_cv": mean_absolute_error(y_ent_n, p)})
    for lr in [0.03, 0.1]:
        for hoja in [20, 50]:
            p = oof_reg(lambda: crear_hgb(lr, hoja), X_ent, y_ent_n, g_ent)
            cv_n.append({"modelo": "Boosting de Poisson", "parametros": f"lr={lr}, hoja={hoja}", "devianza_cv": mean_poisson_deviance(y_ent_n, p), "mae_cv": mean_absolute_error(y_ent_n, p)})
    cv_n = pd.DataFrame(cv_n).sort_values("devianza_cv")
    mejor_n = cv_n.iloc[0]
    say("Modelo de conteo elegido por devianza en CV: " + f"{mejor_n['modelo']} ({mejor_n['parametros']})")
    pn = dict(x.split("=") for x in mejor_n["parametros"].split(", "))
    crear_n = (lambda: crear_poisson(float(pn["alpha"]))) if mejor_n["modelo"] == "Regresión de Poisson" else \
              (lambda: crear_hgb(float(pn["lr"]), int(pn["hoja"])))
    modelo_n = crear_n().fit(X_ent, y_ent_n)
    pred_n_pru = np.clip(modelo_n.predict(X_pru), 1e-6, None)
    media = np.full(len(pru), y_ent_n.mean())
    conteo_eval = {
        "modelo": mejor_n["modelo"], "parametros": mejor_n["parametros"],
        "devianza_prueba": float(mean_poisson_deviance(y_pru_n, pred_n_pru)),
        "mae_prueba": float(mean_absolute_error(y_pru_n, pred_n_pru)),
        "devianza_media": float(mean_poisson_deviance(y_pru_n, media)),
        "mae_media": float(mean_absolute_error(y_pru_n, media)),
        "cafes_reales_prueba": int(y_pru_n.sum()), "cafes_predichos_prueba": float(pred_n_pru.sum()),
        "cv": cv_n.round(4).to_dict(orient="records"),
    }
    say(f"Conteo en prueba: devianza {conteo_eval['devianza_prueba']:.3f} (media {conteo_eval['devianza_media']:.3f}); "
        f"MAE {conteo_eval['mae_prueba']:.3f} (media {conteo_eval['mae_media']:.3f})")
    datos["cafes_esperados"] = oof_reg(crear_n, X_all, datos["n_cafes"], g_all)
    datos["brecha"] = datos["cafes_esperados"] - datos["n_cafes"]

    # ---------------- Clasificación (propuesta v1) ----------------
    umbral_sel = U[seleccionado]
    d = SUPUESTOS["clasificacion"]["delta_cafes"]

    def clasificar(p, brecha, delta=d, umbral=umbral_sel):
        if brecha <= -delta:
            return "Saturada"
        if p < umbral:
            return "Sin demanda"
        if brecha >= delta:
            return "Oportunidad"
        return "En equilibrio"

    datos["clase"] = [clasificar(p, b) for p, b in zip(datos.puntaje, datos.brecha)]
    sens_clases = {}
    for dd in [0.5, 1.0, 1.5]:
        sens_clases[str(dd)] = pd.Series([clasificar(p, b, dd) for p, b in zip(datos.puntaje, datos.brecha)]).value_counts().to_dict()
    say("Clases (delta=1): " + str(datos["clase"].value_counts().to_dict()))

    # ---------------- v2 · Incertidumbre por zona (bootstrap de bloques dentro de cada pliegue) ----------------
    # Para cada pliegue fuera de bloque se reentrenan clasificador y conteo sobre B remuestreos de los
    # bloques de entrenamiento del pliegue. Cada zona recibe B predicciones de modelos que no vieron su bloque.
    B_INC = 100
    rng_u = np.random.default_rng(SEMILLA + 1)
    P_b = np.zeros((len(datos), B_INC))
    E_b = np.zeros((len(datos), B_INC))
    g_vals = g_all.values
    for a, b in GroupKFold(n_splits=K_PLIEGUES).split(X_all, y_all, g_all):
        bl = np.unique(g_vals[a])
        idx_bl = {k: a[g_vals[a] == k] for k in bl}
        for j in range(B_INC):
            sel_i = np.concatenate([idx_bl[k] for k in rng_u.choice(bl, len(bl), replace=True)])
            P_b[b, j] = crear_logistica(C_EL).fit(X_all.iloc[sel_i], y_all.iloc[sel_i]).predict_proba(X_all.iloc[b])[:, 1]
            E_b[b, j] = crear_n().fit(X_all.iloc[sel_i], datos["n_cafes"].iloc[sel_i]).predict(X_all.iloc[b])
    datos["puntaje_p05"] = np.percentile(P_b, 5, axis=1)
    datos["puntaje_p95"] = np.percentile(P_b, 95, axis=1)
    datos["esperados_p05"] = np.percentile(E_b, 5, axis=1)
    datos["esperados_p95"] = np.percentile(E_b, 95, axis=1)
    brecha_b = E_b - datos["n_cafes"].values[:, None]
    clases_b = np.select([brecha_b <= -d, P_b < umbral_sel, brecha_b >= d],
                         ["Saturada", "Sin demanda", "Oportunidad"], "En equilibrio")
    datos["estabilidad_clase"] = (clases_b == datos["clase"].to_numpy(dtype=object)[:, None]).mean(axis=1)
    datos["prob_oportunidad"] = (clases_b == "Oportunidad").mean(axis=1)
    say(f"Incertidumbre: {B_INC} remuestreos por pliegue; estabilidad media de la clase "
        f"{datos['estabilidad_clase'].mean():.2f}; en Oportunidad {datos.loc[datos.clase == 'Oportunidad', 'estabilidad_clase'].mean():.2f}")

    # ---------------- v2 · Índice de sobremesa urbana (propuesta operativa v1) ----------------
    # Definición de la Entrega 1: oficinas, universidades y espacios de permanencia a 300 m.
    # Operacionalización propuesta: promedio de percentiles (0-100) de tres componentes. NO es entrada del modelo.
    rk = lambda s: s.rank(pct=True, method="average")  # noqa: E731
    comp_of = (rk(datos["osm_oficinas_osm_300m"]) + rk(datos["fsq_oficinas_hist_300m"])) / 2
    comp_un = rk(datos["osm_universidades_300m"])
    comp_pe = rk(datos["osm_parques_300m"] + datos["osm_centros_comerciales_300m"])
    datos["isu"] = (100 * (comp_of + comp_un + comp_pe) / 3).round(1)
    q_isu = pd.qcut(datos["isu"].rank(method="first"), 5, labels=["Q1 bajo", "Q2", "Q3", "Q4", "Q5 alto"])
    isu_info = {
        "definicion": "Promedio de percentiles (0–100) de: oficinas a 300 m (OSM y Foursquare), universidades a 300 m "
                      "(OSM) y espacios de permanencia a 300 m (parques + centros comerciales, OSM).",
        "estado": "propuesta v1 · pendiente de validación del equipo",
        "auc_sola": float(roc_auc_score(datos["hay_cafe"], datos["isu"])),
        "por_quintil": datos.groupby(q_isu, observed=True).agg(celdas=("h3", "size"), tasa_cafe=("hay_cafe", "mean"),
                                                             isu_min=("isu", "min"), isu_max=("isu", "max"))
                            .reset_index().rename(columns={"isu": "quintil"}).round(3).to_dict(orient="records"),
    }
    say(f"ISU: AUC sola {isu_info['auc_sola']:.3f}")

    # ---------------- v2 · Calibración del puntaje (fuera de bloque, todas las zonas) ----------------
    cortes = np.linspace(0, 1, 11)
    tramo = pd.cut(datos["puntaje"], cortes, include_lowest=True)
    calib = (datos.groupby(tramo, observed=True).agg(zonas=("h3", "size"), puntaje_medio=("puntaje", "mean"),
                                                    tasa_cafe=("hay_cafe", "mean")).reset_index())
    calib["tramo"] = calib["puntaje"].astype(str)
    calib = calib.drop(columns="puntaje").round(4).to_dict(orient="records")

    # ---------------- Arriendo de referencia (supuesto) ----------------
    sa = SUPUESTOS["arriendo"]
    d_chap = haversine_m(datos.lat.values, datos.lon.values, *sa["ancla_centro"])
    celdas_ancla = datos.loc[d_chap <= sa["ancla_radio_m"], "valor_suelo_m2"]
    mediana_ancla = float(celdas_ancla.median())
    datos["arriendo_ref_millones"] = sa["ancla_millones_mes"] * datos["valor_suelo_m2"] / mediana_ancla
    sa_calc = {"celdas_ancla": int(len(celdas_ancla)), "mediana_suelo_ancla": mediana_ancla,
               "suelo_max_presupuesto": mediana_ancla * sa["presupuesto_max_millones"] / sa["ancla_millones_mes"],
               "celdas_dentro_presupuesto": int((datos["arriendo_ref_millones"] <= sa["presupuesto_max_millones"]).sum())}
    say(f"Arriendo: {sa_calc}")

    # ---------------- Distancias ----------------
    for t, (la, lo) in TIENDAS.items():
        datos[f"dist_{t}"] = haversine_m(datos.lat.values, datos.lon.values, la, lo)
    cols_d = [f"dist_{t}" for t in TIENDAS]
    datos["dist_min_m"] = datos[cols_d].min(axis=1)
    datos["tienda_cercana"] = datos[cols_d].idxmin(axis=1).str.replace("dist_", "", regex=False)

    # ---------------- Razones por celda (contribuciones del modelo final) ----------------
    contrib_all = contribuciones(X_all)
    razones_pos, razones_neg = [], []
    for i in range(len(datos)):
        orden = np.argsort(-contrib_all[i])
        pos = [FEATURES[j] for j in orden if contrib_all[i, j] > 0.02][:3]
        neg = [FEATURES[j] for j in orden[::-1] if contrib_all[i, j] < -0.02][:2]
        razones_pos.append("|".join(pos)); razones_neg.append("|".join(neg))
    datos["factores_a_favor"] = razones_pos
    datos["factores_en_contra"] = razones_neg

    # ---------------- Segmentación (técnica de descubrimiento del cuaderno) ----------------
    vars_cl = ["log_valor_suelo", "ov_comercio_300m", "osm_oficinas_osm_300m", "osm_universidades_300m", "ov_entretenimiento_300m"]
    tmp = datos.copy(); tmp["log_valor_suelo"] = np.log1p(tmp["valor_suelo_m2"])
    Xc = StandardScaler().fit_transform(tmp[vars_cl])
    km = KMeans(n_clusters=4, random_state=SEMILLA, n_init=10).fit(Xc)
    tmp["seg"] = km.labels_
    perfil = tmp.groupby("seg").agg(celdas=("h3", "size"), tasa_cafe=("hay_cafe", "mean"),
                                    comercio=("ov_comercio_300m", "mean"), oficinas=("osm_oficinas_osm_300m", "mean"),
                                    universidades=("osm_universidades_300m", "mean"), suelo=("valor_suelo_m2", "median"))
    nombres = {}
    nombres[perfil["oficinas"].idxmax()] = "Núcleo de oficinas y universidades"
    resto = perfil.drop(index=list(nombres))
    nombres[resto["comercio"].idxmax()] = "Corredor comercial denso"
    resto = resto.drop(index=resto["comercio"].idxmax())
    nombres[resto["suelo"].idxmin()] = "Residencial de baja actividad"
    nombres[resto.drop(index=resto["suelo"].idxmin()).index[0]] = "Barrio mixto"
    datos["segmento"] = tmp["seg"].map(nombres)
    perfil["nombre"] = perfil.index.map(nombres)
    say("Segmentos:\n" + perfil.to_string())

    # ---------------- Valor de la recomendación ----------------
    pm, pr_ = decisiones[seleccionado], decisiones["Regla simple"]

    def estudios_para(n_aptas, pred, idx):
        vp = int(((y_arr[idx] == 1) & (pred[idx] == 1)).sum()); tot = int(pred[idx].sum())
        prec = vp / tot if tot else np.nan
        return n_aptas / prec if prec and prec > 0 else np.nan

    todos = np.arange(len(pru))
    est_m, est_r = estudios_para(2, pm, todos), estudios_para(2, pr_, todos)
    dif_boot = [COSTO_ESTUDIO * (estudios_para(2, pm, s) - estudios_para(2, pr_, s)) for s in muestras]
    valor = {
        "zonas_aptas_objetivo": 2, "costo_estudio_millones": COSTO_ESTUDIO,
        "precision_modelo": float(tabla_por(tabla, seleccionado)["precision"]),
        "precision_regla": float(tabla_por(tabla, "Regla simple")["precision"]),
        "precision_todas": float(tabla_por(tabla, "Estudiarlas todas")["precision"]),
        "estudios_modelo": float(est_m), "estudios_regla": float(est_r),
        "estudios_azar": float(2 / tabla_por(tabla, "Estudiarlas todas")["precision"]),
        "costo_estudios_modelo": float(COSTO_ESTUDIO * est_m), "costo_estudios_regla": float(COSTO_ESTUDIO * est_r),
        "ahorro_vs_regla": float(COSTO_ESTUDIO * (est_r - est_m)),
        "ahorro_vs_regla_ic95": [-x for x in ic([v for v in dif_boot if not np.isnan(v)])][::-1],
        "nota": "‘Apta’ = la zona tiene al menos un café hoy (proxy del target). No es rentabilidad.",
    }
    say(f"Valor: estudios modelo {est_m:.2f} vs regla {est_r:.2f}; ahorro {valor['ahorro_vs_regla']:.1f} M, IC {valor['ahorro_vs_regla_ic95']}")

    # ---------------- Validación con aperturas (si existe el archivo) ----------------
    validacion = {"estado": "pendiente", "motivo": "No se ha entregado el archivo de aperturas abril–septiembre 2026."}
    if ruta_aperturas is not None:
        validacion = validar_aperturas(ruta_aperturas, datos, umbral_sel, d, clasificar, say)


    # ---------------- v2 · Análisis de errores en prueba y datos del simulador de costos ----------------
    mask_pru = (datos["particion"] == "prueba").values
    pred_sel = decisiones[seleccionado]
    tipo = np.select([(y_arr == 1) & (pred_sel == 1), (y_arr == 0) & (pred_sel == 0),
                      (y_arr == 0) & (pred_sel == 1), (y_arr == 1) & (pred_sel == 0)],
                     ["Acierto: con café", "Acierto: descartada", "Falso positivo", "Falso negativo"], "")
    datos["error_prueba"] = ""
    datos.loc[mask_pru, "error_prueba"] = tipo
    tp = datos.loc[mask_pru].copy()
    tp["fn"] = (tp["error_prueba"] == "Falso negativo").astype(int)
    tp["fp"] = (tp["error_prueba"] == "Falso positivo").astype(int)
    tp["suelo_q"] = pd.qcut(datos["valor_suelo_m2"].rank(method="first"), 5,
                           labels=["Q1 más barato", "Q2", "Q3", "Q4", "Q5 más caro"])[mask_pru].values

    def resumen_err(col):
        g = tp.groupby(col, observed=True).agg(zonas=("h3", "size"), tasa_cafe=("hay_cafe", "mean"),
                                               fn=("fn", "sum"), fp=("fp", "sum")).reset_index()
        g["costo"] = COSTO_FN * g["fn"] + COSTO_FP * g["fp"]
        g["costo_por_zona"] = (g["costo"] / g["zonas"]).round(1)
        return g.rename(columns={col: "grupo"}).round(3).to_dict(orient="records")

    errores = {"por_segmento": resumen_err("segmento"), "por_suelo": resumen_err("suelo_q")}

    orden_b = list(bloques_pru)
    bidx = pru["bloque"].map({b: i for i, b in enumerate(orden_b)}).values

    def por_bloque(pred):
        fn = np.bincount(bidx, weights=((y_arr == 1) & (pred == 0)).astype(float), minlength=len(orden_b))
        fp = np.bincount(bidx, weights=((y_arr == 0) & (pred == 1)).astype(float), minlength=len(orden_b))
        return fn.astype(int).tolist(), fp.astype(int).tolist()

    p_oof_ent = oof[("lr", C_EL)]
    sim_lr = []
    for u in UMBRALES:
        pe = (p_oof_ent >= u).astype(int)
        fn_b, fp_b = por_bloque((probas[seleccionado] >= u).astype(int))
        sim_lr.append({"umbral": float(u), "ent_fn": int(((y_ent == 1) & (pe == 0)).sum()),
                       "ent_fp": int(((y_ent == 0) & (pe == 1)).sum()), "fn": fn_b, "fp": fp_b})
    sim_regla = []
    for pa_ in np.arange(0.10, 0.91, 0.05):
        for pb_ in np.arange(0.10, 0.91, 0.05):
            cc = ent["ov_comercio_300m"].quantile(pa_)
            cs = ent["valor_suelo_m2"].quantile(pb_)
            pe = ((ent["ov_comercio_300m"] >= cc) & (ent["valor_suelo_m2"] >= cs)).astype(int).values
            pt_ = ((pru["ov_comercio_300m"] >= cc) & (pru["valor_suelo_m2"] >= cs)).astype(int).values
            fn_b, fp_b = por_bloque(pt_)
            sim_regla.append({"corte_comercio": float(cc), "corte_suelo": float(cs),
                              "ent_fn": int(((y_ent.values == 1) & (pe == 0)).sum()),
                              "ent_fp": int(((y_ent.values == 0) & (pe == 1)).sum()), "fn": fn_b, "fp": fp_b})
    simulador = {
        "bloques": len(orden_b), "semilla_bootstrap": SEMILLA, "n_bootstrap": N_BOOTSTRAP,
        "pos": np.bincount(bidx, weights=(y_arr == 1).astype(float), minlength=len(orden_b)).astype(int).tolist(),
        "neg": np.bincount(bidx, weights=(y_arr == 0).astype(float), minlength=len(orden_b)).astype(int).tolist(),
        "ent_pos": int(y_ent.sum()), "ent_neg": int((y_ent == 0).sum()),
        "modelo": sim_lr, "regla": sim_regla,
    }

    # ---------------- Exportación ----------------
    (RAIZ / "model").mkdir(exist_ok=True)

    cols_out = (["h3", "lat", "lon", "particion", "pliegue_oof", "n_cafes", "puntaje", "cafes_esperados", "brecha", "clase",
                 "arriendo_ref_millones", "dist_min_m", "tienda_cercana"] + cols_d
                + ["factores_a_favor", "factores_en_contra", "segmento", "tm_estacion", "puntaje_p05", "puntaje_p95",
                    "esperados_p05", "esperados_p95", "estabilidad_clase", "prob_oportunidad", "isu", "error_prueba"]
                + FEATURES)
    zonas = datos[cols_out].copy()
    for c in ["puntaje", "cafes_esperados", "brecha", "arriendo_ref_millones", "diversidad_usos", "accesibilidad_transporte",
              "puntaje_p05", "puntaje_p95", "esperados_p05", "esperados_p95", "estabilidad_clase", "prob_oportunidad"]:
        zonas[c] = zonas[c].round(4)
    for c in cols_d + ["dist_min_m", "dist_tm_m"]:
        zonas[c] = zonas[c].round(1)
    assert "nombres_cafes" not in zonas.columns
    zonas.to_csv(RAIZ / "model" / "zonas.csv.gz", index=False, compression="gzip")

    metricas = {
        "generado": date.today().isoformat(),
        "fuente_md5": md5(ruta_datos),
        "particion": {"bloques_entrenamiento": int(ent.bloque.nunique()), "celdas_entrenamiento": len(ent),
                      "cafe_entrenamiento": int(y_ent.sum()), "bloques_prueba": int(pru.bloque.nunique()),
                      "celdas_prueba": len(pru), "cafe_prueba": int(y_arr.sum()),
                      "tasa_base_total": float(datos.hay_cafe.mean()), "tasa_base_ent": float(y_ent.mean()),
                      "tasa_base_prueba": float(y_arr.mean()), "semilla": SEMILLA, "pliegues": K_PLIEGUES,
                      "bootstrap": N_BOOTSTRAP},
        "regla_simple": {"corte_comercio": float(CORTE_COMERCIO), "corte_suelo": float(CORTE_SUELO), "costo_ent": int(costo_regla_ent)},
        "seleccionado": seleccionado, "umbral_seleccionado": umbral_sel,
        "tabla_prueba": tabla, "verificacion_e1": verif,
        "cv_mejores": mejores.reset_index().to_dict(orient="records"),
        "cv_completo": cv.to_dict(orient="records"),
        "curva_costo": curva,
        "importancia_permutacion": imp_perm.round(5).to_dict(orient="records"),
        "importancia_shap": imp_shap.round(5).to_dict(orient="records"),
        "shap_verificacion_error_max": shap_check,
        "beeswarm": beeswarm,
        "puntaje_oof": {"auc_todas": float(roc_auc_score(y_all, p_oof)), "corr_modelo_final_prueba": corr_pru},
        "conteo": conteo_eval,
        "clases": datos["clase"].value_counts().to_dict(),
        "clases_tasa_cafe": datos.groupby("clase")["hay_cafe"].mean().round(3).to_dict(),
        "sensibilidad_clases": sens_clases,
        "arriendo": sa_calc,
        "segmentos": perfil.reset_index().round(3).to_dict(orient="records"),
        "valor": valor,
        "validacion_aperturas": validacion,
        "incertidumbre": {"remuestreos_por_pliegue": B_INC, "metodo": "bootstrap de bloques dentro de cada pliegue fuera de bloque"},
        "isu": isu_info, "calibracion": calib, "errores": errores, "simulador": simulador,
        "log": log,
    }
    (RAIZ / "model" / "metricas.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1, default=_json))
    metadata = {
        "producto": "CaféScore", "version_artefactos": "2026-11-final-v1", "generado": date.today().isoformat(),
        "modelo": seleccionado, "parametros": mejores.loc[seleccionado, "parametros"], "umbral": umbral_sel,
        "columnas": FEATURES, "etiquetas": ETIQUETAS, "tiendas": TIENDAS,
        "costos": {"FN": COSTO_FN, "FP": COSTO_FP, "estudio": COSTO_ESTUDIO},
        "supuestos": SUPUESTOS, "sklearn": sklearn.__version__,
        "fechas_datos": {"cafes": "Overture Maps, septiembre de 2026", "suelo": "Catastro de Bogotá, 2026",
                         "transmilenio": "Validaciones troncales, septiembre de 2025",
                         "foursquare": "Fichas mayormente 2011–2016", "osm": "OpenStreetMap, 2026"},
    }
    (RAIZ / "model" / "app.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=1, default=_json))
    say("Artefactos de la interfaz exportados en model/ (zonas.csv.gz, metricas.json, app.json).")

    # ---------------- Exportación con la ZONA FIJA de la plantilla (exportar.py del profesor) ----------------
    sys.path.insert(0, str(RAIZ))
    from exportar import exportar
    fs = tabla_por(tabla, seleccionado)
    lo, hi = fs["dif_vs_regla_ic95"]
    mostrar = ["lat", "lon", "clase", "isu", "n_cafes", "cafes_esperados", "brecha", "arriendo_ref_millones",
               "dist_min_m", "tienda_cercana", "tm_estacion"]
    tabla_res = datos[["h3"] + mostrar + FEATURES].copy()
    for c in ["cafes_esperados", "brecha", "arriendo_ref_millones"]:
        tabla_res[c] = tabla_res[c].round(2)
    tabla_res["dist_min_m"] = tabla_res["dist_min_m"].round(0)
    exportar(
        modelo=modelo_sel,
        X_entrenamiento=X_ent,
        umbrales=[umbral_sel],
        decisiones=["Descartar por ahora", "Estudiar la zona"],
        metricas={
            "costo_modelo": int(fs["costo"]),
            "costo_regla": int(tabla_por(tabla, "Regla simple")["costo"]),
            "regla_simple": (f"Estudiar solo zonas con al menos {CORTE_COMERCIO:.0f} comercios a 300 m y suelo de al menos "
                             f"COP {CORTE_SUELO:,.0f}/m²".replace(",", ".")),
            "unidad_costo": "en millones de COP (60 por zona con café descartada, 20 por zona sin café estudiada), "
                            f"en {len(pru)} zonas de {pru.bloque.nunique()} bloques de prueba",
            # intervalo del AHORRO (regla − modelo), como lo muestra la plantilla
            "intervalo_diferencia": [float(-hi), float(-lo)],
            "Modelo": f"{seleccionado} ({mejores.loc[seleccionado, 'parametros']})",
            "AUC en prueba": round(float(fs["auc"]), 3),
            "Sensibilidad en prueba": round(float(fs["sensibilidad"]), 3),
            "Precisión en prueba": round(float(fs["precision"]), 3),
            "Conclusión": "El intervalo del ahorro incluye el cero: no se puede afirmar que el modelo le gane a la regla.",
        },
        evento="tener al menos un café",
        tabla_resultados=tabla_res,
        probabilidad_resultados=datos["puntaje"].values,
        columna_id="h3",
        columnas_a_mostrar=mostrar,
        etiquetas={**ETIQUETAS_NEGOCIO, **ETIQUETAS_RESULTADOS},
    )
    say("Modelo exportado con exportar.py de la plantilla (model/pipeline.joblib, metadata.json, resultados.csv).")


def tabla_por(tabla, metodo):
    return next(t for t in tabla if t["metodo"] == metodo)


def validar_aperturas(ruta, datos, umbral, delta, clasificar, say):
    """Validación temporal. Formato esperado (configurable abajo):
    h3, n_cafes_abril (cafés en abril 2026), n_aperturas (aperturas abril–septiembre).
    La clasificación histórica usa la oferta de ABRIL (no la de septiembre) para no usar información futura."""
    ap = pd.read_csv(ruta)
    ren = {c: c.strip().lower() for c in ap.columns}
    ap = ap.rename(columns=ren)
    req = {"h3", "n_cafes_abril", "n_aperturas"}
    if not req.issubset(ap.columns):
        return {"estado": "error", "motivo": f"Columnas esperadas {sorted(req)}; recibidas {sorted(ap.columns)}"}
    m = datos[["h3", "puntaje", "cafes_esperados"]].merge(ap[list(req)], on="h3", how="left")
    m[["n_cafes_abril", "n_aperturas"]] = m[["n_cafes_abril", "n_aperturas"]].fillna(0)
    m["brecha_abril"] = m["cafes_esperados"] - m["n_cafes_abril"]
    m["clase_abril"] = [clasificar(p, b) for p, b in zip(m.puntaje, m.brecha_abril)]
    m["abrio"] = (m["n_aperturas"] > 0).astype(int)
    por_clase = m.groupby("clase_abril").agg(celdas=("h3", "size"), tasa_apertura=("abrio", "mean"),
                                             aperturas=("n_aperturas", "sum")).reset_index()
    # Comparables: celdas que el modelo manda a estudiar (puntaje >= umbral) y no son Oportunidad
    op = m[m.clase_abril == "Oportunidad"]
    comp = m[(m.puntaje >= umbral) & (m.clase_abril != "Oportunidad")]
    rng = np.random.default_rng(SEMILLA)
    difs = []
    for _ in range(N_BOOTSTRAP):
        a = op.sample(len(op), replace=True, random_state=int(rng.integers(1e9)))["abrio"].mean()
        b = comp.sample(len(comp), replace=True, random_state=int(rng.integers(1e9)))["abrio"].mean()
        difs.append(a - b)
    res = {"estado": "completa", "por_clase": por_clase.round(4).to_dict(orient="records"),
           "tasa_oportunidad": float(op["abrio"].mean()), "tasa_comparables": float(comp["abrio"].mean()),
           "dif": float(op["abrio"].mean() - comp["abrio"].mean()),
           "dif_ic95": [float(x) for x in np.percentile(difs, [2.5, 97.5])],
           "n_oportunidad": len(op), "n_comparables": len(comp),
           "nota": "Bootstrap por celdas (no por bloques); las celdas vecinas no son independientes."}
    say(f"Validación aperturas: {res['tasa_oportunidad']:.3f} vs {res['tasa_comparables']:.3f}")
    return res


def _json(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if math.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, tuple):
        return list(o)
    raise TypeError(type(o))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", required=True, type=Path)
    ap.add_argument("--aperturas", type=Path, default=None)
    a = ap.parse_args()
    main(a.datos, a.aperturas)
