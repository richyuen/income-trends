"""AR(1) income process with measurement error, the specification of Choukhmane and de Silva (JF 2026, NBER w32476
Appendix D.4 and Table A3), estimated on our PSID and SIPP samples so the life cycle model can use it instead of
CGM's random walk.

Model for residual log income r (log income minus the deterministic profile, demeaned by year):

    r_it = alpha_i + eta_it + iota_it
    eta_i0 ~ (0, s2_init) at the first age of working life (t = age - start age: 20, or 22 with a college degree)
    eta_it = rho * eta_i,t-1 + xi_it,   Var(xi) = s2_innov
    iota_it ~ (0, s2_me) serially uncorrelated (measurement error and other transitory income)
    alpha_i ~ (0, s2_fe) fixed effect: zero in the Choukhmane-de Silva spec ("cds"), free in the "fe" spec

    Cov(r_t, r_t+d) = s2_fe + rho^d * Var(eta_t) + s2_me * 1{d = 0}
    Var(eta_t) = rho^(2t) * s2_init + s2_innov * (1 - rho^(2t)) / (1 - rho^2)

Specs: cds (alpha = 0; rho, s2_init, s2_innov, s2_me), fe (adds s2_fe), rw (rho = 1, alpha = 0: the CGM random
walk plus transitory shock in the same moment framework, s2_innov = s2_perm and s2_me = s2_trans).

Estimation: equally weighted minimum distance on the autocovariances of r by t (years since start age) and lag d
(calendar years, 0..max_d; the PSID's biennial waves after 1997 give even lags only), cells with at least
MIN_PAIRS pairs, as in Guvenen (2009) and Choukhmane-de Silva's two-step approach. The first step is the project's
fixed-effects age profile (incproc.fe_regression, with marital status and household size for CGM income), so the
profile is the same one already in the dataset. SEs: Poisson bootstrap by person (residuals held fixed).

Samples:
  psid   cgm (household income, default sample) and head_earn (head's own labor income), periods full 1969-2022,
         cgm 1969-1991, p4 2007-2022; cuts all and education
  sipp   men's own earnings (census_extend.sipp_load sample), old design 1995-2013 and new design 2013-2024, all
         and education; plus the 1996 panel alone, and its job stayers (same main employer every year, main-job
         earnings), the closest match to Choukhmane-de Silva's SIPP 1996 sample of workers in the same job.
         SIPP panels run 2-4 years, so rho is identified only from lags 1-3 and the rise of variance with age.

Usage: python3 -I extend/scripts/ar1_process.py [PANEL_DIR] [psid] [sipp]   (PSID about 25 minutes, SIPP a few)
Writes extend/output/ar1_estimates.csv and ar1_moments.csv (data and fitted autocovariances).
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import incproc as ip  # noqa: E402
import psid_extend as pe  # noqa: E402
import census_extend as ce  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "extend", "output")
ARGS = [a for a in sys.argv[1:] if a not in ("psid", "sipp")]
SOURCES = [a for a in sys.argv[1:] if a in ("psid", "sipp")] or ["psid", "sipp"]
PANEL = ARGS[0] if ARGS else "/mnt/project-files/psid"
MIN_PAIRS = 30
N_BOOT = 100
START = {1: 20, 2: 20, 3: 22}
SPECS = ("cds", "fe", "rw")
NAMES = ("rho", "s2_init", "s2_innov", "s2_me", "s2_fe")


# ---------------------------------------------------------------- moments
def pair_table(unit, t, year, r, max_d):
    """All within-unit pairs (t of the earlier year, lag d in calendar years, product r*r'), d = 0..max_d."""
    D = pd.DataFrame({"unit": unit, "t": t, "year": year, "r": r})
    m = D.merge(D[["unit", "year", "r"]], on="unit", suffixes=("", "_f"))
    m["d"] = m["year_f"] - m["year"]
    m = m[(m["d"] >= 0) & (m["d"] <= max_d)]
    return pd.DataFrame({"unit": m["unit"].to_numpy(), "t": m["t"].to_numpy(), "d": m["d"].to_numpy(),
                         "p": (m["r"] * m["r_f"]).to_numpy()})


def cell_moments(P):
    """Per (unit, cell) sums, the cell list (cells with at least MIN_PAIRS pairs) and the data moments."""
    C = P.groupby(["t", "d"])["p"].agg(n="size", m="mean").reset_index()
    C = C[C["n"] >= MIN_PAIRS].reset_index(drop=True)
    P = P.merge(C[["t", "d"]].reset_index(), on=["t", "d"])
    U = P.groupby(["unit", "index"])["p"].agg(n="size", s="sum").reset_index()
    return C, U


# ---------------------------------------------------------------- model
def full_params(x, spec):
    if spec == "cds":
        return dict(rho=x[0], s2_init=x[1], s2_innov=x[2], s2_me=x[3], s2_fe=0.0)
    if spec == "fe":
        return dict(rho=x[0], s2_init=x[1], s2_innov=x[2], s2_me=x[3], s2_fe=x[4])
    return dict(rho=1.0, s2_init=x[0], s2_innov=x[1], s2_me=x[2], s2_fe=0.0)


def model_cov(q, t, d):
    rho = q["rho"]
    if abs(1 - rho) < 1e-9:
        v = q["s2_init"] + q["s2_innov"] * t
    else:
        r2t = rho ** (2 * t)
        v = r2t * q["s2_init"] + q["s2_innov"] * (1 - r2t) / (1 - rho ** 2)
    return q["s2_fe"] + rho ** d * v + q["s2_me"] * (d == 0)


def fit(t, d, m, spec, x0=None):
    if spec == "cds":
        lo, hi, start = [0, 0, 0, 0], [1.0, 5, 1, 1], [0.95, 0.1, 0.02, 0.05]
    elif spec == "fe":
        lo, hi, start = [0, 0, 0, 0, 0], [1.0, 5, 1, 1, 5], [0.9, 0.05, 0.02, 0.05, 0.05]
    else:
        lo, hi, start = [0, 0, 0], [5, 1, 1], [0.1, 0.01, 0.05]
    def res(x):
        return model_cov(full_params(x, spec), t, d) - m

    if x0 is not None:                       # bootstrap draws: start from the point estimate
        sol = least_squares(res, np.clip(x0, lo, hi), bounds=(lo, hi), x_scale="jac")
        return sol.x, float((sol.fun ** 2).sum())
    starts = [start]                         # point estimate: several starts, keep the best (the fit is not convex)
    if spec != "rw":
        for rho0 in (0.5, 0.8, 0.95, 0.99):
            for fe0 in ((0.0, 0.1) if spec == "fe" else (None,)):
                s0 = list(start)
                s0[0] = rho0
                if fe0 is not None:
                    s0[4] = fe0
                starts.append(s0)
    best = None
    for s0 in starts:
        sol = least_squares(res, np.clip(s0, lo, hi), bounds=(lo, hi), x_scale="jac")
        if best is None or sol.cost < best.cost:
            best = sol
    return best.x, float((best.fun ** 2).sum())


def estimate(unit, person, t, year, r, max_d, specs=SPECS, n_boot=N_BOOT, seed=0):
    P = pair_table(unit, t, year, r, max_d)
    C, U = cell_moments(P)
    tt, dd, mm = C["t"].to_numpy(float), C["d"].to_numpy(float), C["m"].to_numpy()
    # bootstrap draws of the cell moments: Poisson(1) weights by person
    pmap = pd.Series(person, index=unit).groupby(level=0).first()
    pid, puniq = pd.factorize(U["unit"].map(pmap))
    rng = np.random.default_rng(seed)
    nc = len(C)
    boots = []
    for _ in range(n_boot):
        w = rng.poisson(1.0, len(puniq))[pid]
        n = np.bincount(U["index"], w * U["n"], nc)
        s = np.bincount(U["index"], w * U["s"], nc)
        boots.append(np.where(n > 0, s / np.maximum(n, 1), mm))
    out, fitted = [], {}
    for spec in specs:
        x, ssr = fit(tt, dd, mm, spec)
        draws = np.array([fit(tt, dd, b, spec, x0=x)[0] for b in boots])
        q = full_params(x, spec)
        qs = [full_params(b, spec) for b in draws]
        row = dict(spec=spec, ssr=ssr, n_moments=nc, n_pairs=int(C["n"].sum()), max_d_used=int(C["d"].max()),
                   max_t_used=int(C["t"].max()), **q)
        for k in NAMES:
            row[f"{k}_se"] = float(np.std([b[k] for b in qs], ddof=1)) if n_boot > 1 else np.nan
        rho = q["rho"]
        row["half_life"] = np.log(0.5) / np.log(rho) if 0 < rho < 1 else np.inf
        row["var_eta_stationary"] = q["s2_innov"] / (1 - rho ** 2) if rho < 1 else np.inf
        for a in (45, 65):              # Var(eta) at these ages for a start age of 20
            row[f"var_eta_{a}"] = model_cov(dict(q, s2_fe=0.0, s2_me=0.0), a - 20, 1) / (rho if rho > 0 else 1)
        out.append(row)
        fitted[spec] = model_cov(q, tt, dd)
    M = C.assign(**{f"fit_{s}": v for s, v in fitted.items()})
    return out, M


def residuals(G, controls, time):
    """Fixed-effects profile (as in the dataset), residual log income demeaned by year."""
    _, st, fhat, _ = ip.fe_regression(G, controls=controls)
    r = G["logy"] - fhat
    return r - r.groupby(G[time]).transform("mean")


# ---------------------------------------------------------------- samples
def psid_runs():
    pe.PANEL = PANEL                         # psid_extend reads sys.argv[1] at import, which may be "psid" here
    F = pe.load()
    rows, mom = [], []
    for measure in ["cgm", "head_earn"]:
        S = pe.base_sample(F, measure, pe.FLOOR)
        periods = ["full", "cgm", "p4"] if measure == "cgm" else ["full"]
        for period in periods:
            W = S[S["income_year"].between(*pe.PERIODS[period])].copy()
            W["g_all"] = "all"
            W["g_education"] = W["educ3_h"].map(pe.EDUC)
            max_d = 20 if period in ("full", "cgm") else 14
            for cut in ["all", "education"]:
                for grp, G in W.groupby(f"g_{cut}"):
                    r = residuals(G, pe.CONTROLS[measure], "income_year")
                    t = (G["age"] - G["educ3_h"].map(START)).to_numpy()
                    res, M = estimate(G["unit"].to_numpy(), G["person"].to_numpy(), t, G["income_year"].to_numpy(),
                                      r.to_numpy(), max_d)
                    key = dict(source="psid", measure=measure, period=period,
                               years="-".join(map(str, pe.PERIODS[period])), cut=cut, group=grp,
                               n_units=G["unit"].nunique(), n_obs=len(G))
                    rows += [dict(key, **x) for x in res]
                    mom.append(M.assign(**key))
                    print(f"  psid {measure} {period} {cut} {grp}: rho={res[0]['rho']:.3f}", flush=True)
    return rows, mom


def sipp_runs():
    S = ce.sipp_load()
    raw = pd.read_parquet(os.path.join(ROOT, "sipp", "data", "sipp_py_old_1996.parquet"),
                          columns=["pid", "year", "main_earn", "n_jobs"])
    rows, mom = [], []
    plan = [("old_1995_2013", S[S["era"] == "old_1995_2013"], ["all", "education"]),
            ("new_2013_2024", S[S["era"] == "new_2013_2024"], ["all", "education"]),
            ("panel_1996", S[S["panel"].astype(str) == "1996"], ["all"])]
    # job stayers in the 1996 panel: same main employer (not a business) and one job in every year; main-job earnings
    P96 = S[S["panel"].astype(str) == "1996"].merge(raw, on=["pid", "year"], how="left")
    P96 = P96[(P96["main_jobkey"] < 100) & (P96["n_jobs"] == 1)]
    same = P96.groupby("person")["main_jobkey"].transform("nunique") == 1
    P96 = P96[same].copy()
    P96["y"] = P96["main_earn"] / P96["year"].map(ce.cpi_factor()) / 1000
    P96 = P96[P96["y"] >= ce.FLOOR].copy()
    P96["logy"] = np.log(P96["y"])
    plan.append(("panel_1996_stayers", P96, ["all"]))
    for name, W, cuts in plan:
        for cut in cuts:
            for grp, G in W.dropna(subset=[f"g_{cut}"]).groupby(f"g_{cut}"):
                G = G[G.groupby("unit")["year"].transform("size") >= 2]
                r = residuals(G, (), "year")
                t = (G["age"] - G["educ3"].map(START)).to_numpy()
                res, M = estimate(G["unit"].to_numpy(), G["person"].to_numpy(), t, G["year"].to_numpy(),
                                  r.to_numpy(), 4)
                key = dict(source="sipp", measure="person_earn" if "stayers" not in name else "main_job_earn",
                           period=name, years=f"{G['year'].min()}-{G['year'].max()}", cut=cut, group=grp,
                           n_units=G["unit"].nunique(), n_obs=len(G))
                rows += [dict(key, **x) for x in res]
                mom.append(M.assign(**key))
                print(f"  sipp {name} {cut} {grp}: rho={res[0]['rho']:.3f}", flush=True)
    return rows, mom


def main():
    """Runs the requested sources (default both) and replaces their rows in the output files."""
    os.makedirs(OUT, exist_ok=True)
    for src in SOURCES:
        rows, mom = psid_runs() if src == "psid" else sipp_runs()
        for name, new in [("ar1_estimates.csv", pd.DataFrame(rows)), ("ar1_moments.csv", pd.concat(mom))]:
            path = os.path.join(OUT, name)
            if os.path.exists(path):
                old = pd.read_csv(path)
                new = pd.concat([old[old["source"] != src], new], ignore_index=True)
            new.sort_values(["source"], kind="stable").to_csv(path, index=False, float_format="%.6g")


if __name__ == "__main__":
    main()
