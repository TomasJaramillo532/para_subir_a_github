"""Simulador de supuestos de costo. Reproduce la metodología del cuaderno con otros costos:
umbral y cortes de la regla se eligen en ENTRENAMIENTO; la prueba solo mide. Sin Streamlit."""
from __future__ import annotations

import numpy as np


def matriz_bootstrap(n_bloques: int, n: int = 1000, semilla: int = 2559) -> np.ndarray:
    """Conteos (n × bloques) de cada bloque en cada remuestreo; mismas muestras que el pipeline."""
    rng = np.random.default_rng(semilla)
    m = np.zeros((n, n_bloques), dtype=int)
    for i in range(n):
        np.add.at(m[i], rng.choice(n_bloques, size=n_bloques, replace=True), 1)
    return m


def _costo_bloques(fn, fp, cfn, cfp):
    return cfn * np.asarray(fn) + cfp * np.asarray(fp)


def simular(sim: dict, cfn: float, cfp: float, boot: np.ndarray) -> dict:
    # Modelo: umbral que minimiza el costo fuera de pliegue en entrenamiento (primer mínimo, como el cuaderno)
    ent_m = [cfn * r["ent_fn"] + cfp * r["ent_fp"] for r in sim["modelo"]]
    im = int(np.argmin(ent_m))
    rm = sim["modelo"][im]
    # Regla: cortes que minimizan el costo en entrenamiento (desempate como min() de tuplas del cuaderno)
    cand = [(cfn * r["ent_fn"] + cfp * r["ent_fp"], r["corte_comercio"], r["corte_suelo"], k) for k, r in enumerate(sim["regla"])]
    ir = min(cand)[3]
    rr = sim["regla"][ir]
    cb_m = _costo_bloques(rm["fn"], rm["fp"], cfn, cfp)
    cb_r = _costo_bloques(rr["fn"], rr["fp"], cfn, cfp)
    cb_todas = cfp * np.asarray(sim["neg"])
    cb_ninguna = cfn * np.asarray(sim["pos"])
    out = {"umbral": rm["umbral"], "umbral_teorico": cfp / (cfp + cfn),
           "corte_comercio": rr["corte_comercio"], "corte_suelo": rr["corte_suelo"]}
    for nombre, cb in [("modelo", cb_m), ("regla", cb_r), ("todas", cb_todas), ("ninguna", cb_ninguna)]:
        bs = boot @ cb
        out[nombre] = {"costo": float(cb.sum()), "ic": np.percentile(bs, [2.5, 97.5]).tolist()}
    dif = boot @ (cb_m - cb_r)
    out["dif"] = float((cb_m - cb_r).sum())
    out["dif_ic"] = np.percentile(dif, [2.5, 97.5]).tolist()
    out["modelo"].update({"fn": int(sum(rm["fn"])), "fp": int(sum(rm["fp"]))})
    out["regla"].update({"fn": int(sum(rr["fn"])), "fp": int(sum(rr["fp"]))})
    return out


def precision_bootstrap(sim: dict, umbral: float, boot: np.ndarray) -> tuple[float, list[float]]:
    """Precisión del modelo en prueba y su IC 95 % por bootstrap de bloques."""
    r = next(x for x in sim["modelo"] if abs(x["umbral"] - umbral) < 1e-9)
    fp = np.asarray(r["fp"]); fn = np.asarray(r["fn"]); pos = np.asarray(sim["pos"])
    vp = pos - fn
    prec = vp.sum() / (vp.sum() + fp.sum())
    num, den = boot @ vp, boot @ (vp + fp)
    ps = np.where(den > 0, num / np.maximum(den, 1), np.nan)
    return float(prec), np.nanpercentile(ps, [2.5, 97.5]).tolist()
