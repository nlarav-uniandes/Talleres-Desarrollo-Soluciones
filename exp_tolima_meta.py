"""
Avance 1 segun la propuesta entregada: Tolima y Meta, 66 municipios endemicos.

Particion por anio objetivo: entrenamiento <= 2021, validacion 2022-2023,
prueba 2024-2025. Canal, SIR, endemicidad y etiqueta se recalculan por
particion con solo anios anteriores: referencia 2007-2021 para entrenamiento y
validacion, 2007-2023 para prueba. Tres familias (boosting XGBoost/LightGBM,
GAM, logistica regularizada), Platt sobre validacion, umbral elegido en
validacion con la regla de la propuesta (falsas alarmas <= canal + 5 pp).
Ablacion por grupos de variables con XGBoost.
Uso: python -I exp_tolima_meta.py <repo> <salida>
"""
import json
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from pygam import LogisticGAM, s, f
from sklearn.calibration import calibration_curve
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO))
from src.features.build_features import aplicar_referencia  # noqa: E402

CASOS = [f"casos_{t}_lag_{r}" for t in ("clasico", "grave") for r in (1, 2, 3, 4, 6)] + \
        ["casos_clasico_roll3", "casos_grave_roll3"]
CANAL = ["p25", "p75", "zona_canal", "sir", "brote", "brote_lag_1",
         "p25_objetivo", "p75_objetivo", "zona_objetivo"]
ESTAC = ["mes_sin", "mes_cos"]
CLIMA = ["temp_mean_c", "dewpoint_mean_c", "rain_mm_day", "soil_water_l1_mean",
         "surface_runoff_mm_day", "total_evaporation_mm_day_ecmwf", "wind_u_mean_ms",
         "wind_v_mean_ms", "solar_radiation_mj_m2_day",
         "temp_mean_c_lag_1", "temp_mean_c_lag_2", "temp_mean_c_lag_3",
         "rain_mm_day_lag_1", "rain_mm_day_lag_2", "rain_mm_day_lag_3"]
TODAS = CASOS + CANAL + ESTAC + CLIMA


def particiones(h):
    d = pd.read_parquet(REPO / "data/processed/features_mensual.parquet")
    d = d[d.departamento.isin(["TOLIMA", "META"])]
    a = aplicar_referencia(d, ref_fin=2021, horizonte=h)
    b = aplicar_referencia(d, ref_fin=2023, horizonte=h)
    munis = set(a.loc[a.es_endemico == 1, "divipola"])

    def prep(x):
        x = x[x.divipola.isin(munis) & x.objetivo.notna()].copy()
        x["objetivo"] = x.objetivo.astype(int); x["es_inicio"] = x.es_inicio.astype(int)
        return x
    a, b = prep(a), prep(b)
    return (a[a.anio_objetivo <= 2021], a[a.anio_objetivo.between(2022, 2023)],
            b[b.anio_objetivo.between(2024, 2025)], len(munis))


def metr(y, p, ini):
    vp = int(((y == 1) & (p == 1)).sum()); fn = int(((y == 1) & (p == 0)).sum())
    fp = int(((y == 0) & (p == 1)).sum()); vn = int(((y == 0) & (p == 0)).sum())
    mi = (y == 1) & (ini == 1)
    return dict(sens=vp / max(vp + fn, 1), prec=vp / max(vp + fp, 1), far=fp / max(fp + vn, 1),
                f1=2 * vp / max(2 * vp + fp + fn, 1), inicios=int(mi.sum()),
                ini_det=int(p[mi].sum()), sens_ini=float(p[mi].mean()) if mi.any() else np.nan)


def canal_pred(x):
    return (x.zona_objetivo == 2).astype(int).values


def razon(x):
    return (x.casos_clasico / x.p75_objetivo.where(x.p75_objetivo > 0, 1.0)).values


def ajustar(nombre, tr, va, cols):
    Xtr, Xva = tr[cols], va[cols]
    if nombre == "XGBoost":
        m = xgb.XGBClassifier(n_estimators=500, max_depth=4, learning_rate=0.05, subsample=0.8,
                              colsample_bytree=0.8, eval_metric="aucpr", early_stopping_rounds=40,
                              tree_method="hist", random_state=42, n_jobs=-1)
        m.fit(Xtr, tr.objetivo, eval_set=[(Xva, va.objetivo)], verbose=False)
    elif nombre == "LightGBM":
        m = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.05, num_leaves=15, min_child_samples=40,
                               subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                               random_state=42, verbose=-1)
        m.fit(Xtr, tr.objetivo, eval_set=[(Xva, va.objetivo)], callbacks=[lgb.early_stopping(40, verbose=False)])
    elif nombre == "Logistica L2":
        best = None
        for C in (0.01, 0.1, 1.0):
            mm = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                               LogisticRegression(C=C, max_iter=2000)).fit(Xtr, tr.objetivo)
            sc = average_precision_score(va.objetivo, mm.predict_proba(Xva)[:, 1])
            if best is None or sc > best[0]:
                best = (sc, mm)
        m = best[1]
    else:  # GAM: splines en variables continuas, factor en la zona
        imp = make_pipeline(SimpleImputer(strategy="median"), StandardScaler()).fit(Xtr)
        cont = [i for i, c in enumerate(cols) if c not in ("zona_canal", "zona_objetivo", "brote", "brote_lag_1")]
        term = s(cont[0], n_splines=6)
        for i in cont[1:]:
            term += s(i, n_splines=6)
        for i, c in enumerate(cols):
            if i not in cont:
                term += f(i) if c.startswith("zona") else s(i, n_splines=4)
        best = None
        for lam in (1, 10, 100):
            g = LogisticGAM(term, lam=lam, max_iter=200).fit(imp.transform(Xtr), tr.objetivo.values)
            sc = average_precision_score(va.objetivo, g.predict_proba(imp.transform(Xva)))
            if best is None or sc > best[0]:
                best = (sc, g)
        g = best[1]

        class W:
            def predict_proba(self, X):
                p = g.predict_proba(imp.transform(X)); return np.c_[1 - p, p]
        m = W()
    return m


def evaluar(m, cols, tr, va, te):
    rv, rt = m.predict_proba(va[cols])[:, 1], m.predict_proba(te[cols])[:, 1]
    pl = LogisticRegression().fit(rv.reshape(-1, 1), va.objetivo)
    cv, ct = pl.predict_proba(rv.reshape(-1, 1))[:, 1], pl.predict_proba(rt.reshape(-1, 1))[:, 1]
    yv, iv, yt, it = va.objetivo.values, va.es_inicio.values, te.objetivo.values, te.es_inicio.values
    tope = metr(yv, canal_pred(va), iv)["far"] + 0.05
    grid = np.unique(np.quantile(cv, np.linspace(0, 1, 400)))
    ok = [u for u in grid if metr(yv, (cv >= u).astype(int), iv)["far"] <= tope]
    u = min(ok)
    r = metr(yt, (ct >= u).astype(int), it)
    neg = (yt == 0) | (it == 1)
    r |= dict(umbral=float(u), auroc=roc_auc_score(yt, ct), prauc=average_precision_score(yt, ct),
              auroc_ini=roc_auc_score(yt[neg], ct[neg]), brier_raw=brier_score_loss(yt, rt),
              brier_cal=brier_score_loss(yt, ct))
    # mismo FAR que el canal en prueba (comparacion de curva)
    far_c = metr(yt, canal_pred(te), it)["far"]
    sn = np.sort(ct[yt == 0])[::-1]; uc = sn[min(int(far_c * len(sn)), len(sn) - 1)]
    rc = metr(yt, (ct > uc).astype(int), it)
    r |= dict(ini_det_farcanal=rc["ini_det"], sens_ini_farcanal=rc["sens_ini"])
    return r, ct, (ct >= u).astype(int)


res = {}
for h in (1, 2):
    tr, va, te, nm = particiones(h)
    yt, it = te.objetivo.values, te.es_inicio.values
    info = dict(munis=nm, tr=len(tr), va=len(va), te=len(te), ini_tr=int(tr.es_inicio.sum()),
                ini_va=int(va.es_inicio.sum()), ini_te=int(it.sum()),
                prev_tr=tr.objetivo.mean(), prev_va=va.objetivo.mean(), prev_te=te.objetivo.mean(),
                clima_na=float(te[CLIMA[:9]].isna().mean().max()))
    filas, cal, preds = {}, {}, {}
    for n in ("XGBoost", "LightGBM", "GAM", "Logistica L2"):
        m = ajustar(n, tr, va, TODAS)
        filas[n], ct, preds[n] = evaluar(m, TODAS, tr, va, te)
        cal[n] = ct
        if n == "XGBoost" and h == 1:
            imp = pd.Series(m.feature_importances_, TODAS).sort_values(ascending=False)
    rz = razon(te)
    for n, p in (("Canal endemico", canal_pred(te)), ("Persistencia", te.brote.astype(int).values)):
        r = metr(yt, p, it); neg = (yt == 0) | (it == 1)
        r |= dict(auroc=roc_auc_score(yt, rz), prauc=average_precision_score(yt, rz),
                  auroc_ini=roc_auc_score(yt[neg], rz[neg]))
        filas[n] = r; preds[n] = p
    # ablacion con XGBoost
    abl = {}
    for n, cols in (("Solo historial de casos", CASOS), ("+ canal endemico", CASOS + CANAL),
                    ("+ estacionalidad", CASOS + CANAL + ESTAC), ("+ clima (todas)", TODAS),
                    ("Casos + estacionalidad + clima, sin canal", CASOS + ESTAC + CLIMA)):
        m = ajustar("XGBoost", tr, va, cols)
        abl[n] = evaluar(m, cols, tr, va, te)[0]
    # por periodo
    per = []
    for a in (2024, 2025):
        mk = (te.anio_objetivo == a).values
        for n in ("XGBoost", "LightGBM", "GAM", "Logistica L2", "Canal endemico", "Persistencia"):
            r = metr(yt[mk], preds[n][mk], it[mk])
            per.append(dict(h=h, anio=a, modelo=n, prev=yt[mk].mean(), **r))
    res[h] = dict(info=info, tabla=filas, ablacion=abl, periodo=per)
    print(f"\n==== T+{h}", json.dumps(info, default=float))
    print(pd.DataFrame(filas).T[["auroc", "auroc_ini", "sens", "far", "ini_det", "sens_ini",
                                 "ini_det_farcanal", "brier_raw", "brier_cal"]].round(3).to_string())
    print(pd.DataFrame(abl).T[["auroc", "auroc_ini", "far", "ini_det", "sens_ini", "ini_det_farcanal"]].round(3).to_string())
    print(pd.DataFrame(per)[["anio", "modelo", "prev", "far", "ini_det", "inicios", "sens_ini"]].round(3).to_string())
    if h == 1:
        print(imp.head(12).round(3).to_string())
        fig, ax = plt.subplots(figsize=(5.8, 4))
        imp.head(12)[::-1].plot.barh(ax=ax, color="#3b6ea8")
        ax.set_xlabel("Importancia (ganancia relativa)"); ax.set_title("XGBoost T+1: 12 variables más importantes", fontsize=10)
        fig.tight_layout(); fig.savefig(OUT / "tm_importancia.png", dpi=160); plt.close(fig)
        fig, ax = plt.subplots(figsize=(4.8, 4))
        for n, c, ls in (("XGBoost", "#1f4e8c", "-"), ("GAM", "#e0a030", "--"), ("Logistica L2", "#7f7f7f", ":")):
            fp, mp = calibration_curve(yt, cal[n], n_bins=10)
            ax.plot(mp, fp, color=c, ls=ls, marker="o", ms=3, label=n.replace("Logistica", "Logística"))
        ax.plot([0, 1], [0, 1], "k--", lw=0.7); ax.set_xlabel("Probabilidad predicha (calibrada)")
        ax.set_ylabel("Frecuencia observada"); ax.set_title("Calibración en prueba 2024-2025, T+1", fontsize=10)
        ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(OUT / "tm_calibracion.png", dpi=160); plt.close(fig)
json.dump(res, open(OUT / "tm_resultados.json", "w"), default=float, indent=1)
