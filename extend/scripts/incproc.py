"""Shared estimators for the CGM (2005) income process, generalized for subgroups, periods and data sources.

log Y_it = f(age_it, Z_it) + alpha_i + v_it + e_it, v_it = v_i,t-1 + u_it (permanent), e_it transitory.

  fe_regression   within (fixed-effects) regression of log income on age dummies and controls (CGM Table 1)
  poly_fit        cubic in age, age^2/10, age^3/100 fitted to the age dummies (CGM Table 2)
  cs_variances    Carroll-Samwick decomposition Var(r_d) = d*s2_perm + 2*s2_trans, r_d = u_{t+d} - u_t, with
                  d in calendar years (works for the biennial PSID waves after 1997 and for short SIPP panels);
                  OLS of the per-lag variances on d (CGM Appendix B, Eq. 19) with a unit-level Poisson bootstrap SE
  industry_sector harmonized 7-sector industry from Census 1970/1980/1990 (3-digit) and 2000-2017 (4-digit) codes

The same functions as cgm/scripts/replicate.py, written for any sample: cgm/ stays the frozen replication.
"""
import numpy as np
import pandas as pd

SECTORS = {1: "agri_mining_construction", 2: "manufacturing", 3: "trade", 4: "transport_utilities_info",
           5: "finance_business_services", 6: "education_health_other_services", 7: "public_administration"}


def industry_sector(code, four_digit):
    """Map Census industry codes to 7 broad sectors (NaN for military, not specified or invalid).

    three-digit (Census 1970, 1980, 1990 codes; PSID 1968-2001, CPS ASEC 1988-2002, SIPP 1996-2001):
      <40 agriculture/forestry/fishing, 40-59 mining, 60-99 construction, 100-399 manufacturing, 400-499
      transportation/communications/utilities, 500-699 wholesale and retail, 700-719 FIRE, 720-760 business
      and repair services, 761-899 personal, entertainment, professional (health, education, legal ...),
      900-939 public administration.
    four-digit (Census 2000/2002/2007/2012/2017 codes, PSID 2003-2015 given as code/10):
      <300 agriculture, <500 mining, <700 utilities, <1000 construction, <4000 manufacturing, <6000 wholesale
      and retail, <6800 transportation, warehousing and information, <7200 FIRE, <7800 professional,
      scientific, management and administrative services, <9300 education, health, leisure and other
      services, <9600 public administration.
    Known seam: legal, engineering and accounting services sit in sector 6 in the 3-digit systems and in
    sector 5 in the 4-digit systems.
    """
    c = pd.to_numeric(pd.Series(code), errors="coerce").to_numpy(float)
    four = np.broadcast_to(np.asarray(four_digit, bool), c.shape)
    out = np.full(c.shape, np.nan)
    # three-digit
    b3 = [(1, 40, 1), (40, 100, 1), (100, 400, 2), (400, 500, 4), (500, 700, 3), (700, 761, 5), (761, 900, 6),
          (900, 940, 7)]
    b4 = [(1, 700, 1), (770, 1000, 1), (570, 700, 4), (1000, 4000, 2), (4000, 6000, 3), (6000, 6800, 4),
          (6800, 7800, 5), (7800, 9300, 6), (9300, 9600, 7)]
    for lo, hi, s in b3:
        out[~four & (c >= lo) & (c < hi)] = s
    for lo, hi, s in b4:                      # utilities (570-690) after mining/agri: overrides to sector 4
        out[four & (c >= lo) & (c < hi)] = s
    return out


def within(x, g):
    return x - x.groupby(g).transform("mean")


def fe_regression(S, controls=("married", "hhcomp"), y="logy", unit="unit", age="age"):
    """Within estimator of log income on age dummies (youngest age omitted) and controls, by unit.

    Returns coef table (conventional SEs), stats (const in the Stata xtreg, fe convention), fitted deterministic
    part without the fixed effect (Series on S.index), and the age-dummy profile (Series by age, youngest = 0).
    """
    ages = np.sort(S[age].unique())
    X = pd.DataFrame({f"age{a}": (S[age] == a).astype(float) for a in ages[1:]}, index=S.index)
    for c in controls:
        X[c] = S[c].astype(float)
    Xd = X.apply(lambda col: within(col, S[unit])).to_numpy()
    yd = within(S[y], S[unit]).to_numpy()
    b, *_ = np.linalg.lstsq(Xd, yd, rcond=None)
    e = yd - Xd @ b
    N, k, n = len(S), X.shape[1], S[unit].nunique()
    dof = N - n - k
    s2 = e @ e / dof
    XtX_inv = np.linalg.pinv(Xd.T @ Xd)
    se = np.sqrt(np.clip(np.diag(XtX_inv) * s2, 0, None))
    r2w = 1 - (e @ e) / (yd @ yd)
    const = S[y].mean() - X.mean().to_numpy() @ b
    coef = pd.DataFrame({"coef": b, "se": se}, index=X.columns)
    fhat = pd.Series(X.to_numpy() @ b, index=S.index)
    prof = pd.Series({ages[0]: 0.0, **{a: coef.loc[f"age{a}", "coef"] for a in ages[1:]}}).sort_index()
    stats = dict(n_units=n, n_obs=N, Tbar=N / n, s2e=s2, r2_within=r2w, const=const,
                 **{c: coef.loc[c, "coef"] for c in controls}, **{f"{c}_se": coef.loc[c, "se"] for c in controls},
                 **{f"mean_{c}": S[c].mean() for c in controls})
    return coef, stats, fhat, prof


def poly_fit(prof, order=3):
    a = prof.index.to_numpy(float)
    Z = np.column_stack([np.ones_like(a)] + [a ** p / 10 ** (p - 1) for p in range(1, order + 1)])
    c, *_ = np.linalg.lstsq(Z, prof.to_numpy(), rcond=None)
    return c, pd.Series(Z @ c, index=prof.index)


def poly_eval(c, ages):
    a = np.asarray(ages, float)
    return sum(c[p] * a ** p / 10 ** max(p - 1, 0) for p in range(len(c)))


def profile_summary(c3, prof):
    """Peak age, growth from the youngest age to the peak (ratio), fall from peak to 65 and changes between fixed
    ages (log points) of the cubic."""
    grid = np.arange(int(prof.index.min()), int(prof.index.max()) + 1)
    f = poly_eval(c3, grid)
    out = dict(age_min=int(grid[0]), age_max=int(grid[-1]), peak_age=int(grid[np.argmax(f)]),
               growth_to_peak=float(np.exp(f.max() - f[0])))
    out["fall_peak_to_65"] = float(f.max() - poly_eval(c3, [65])[0]) if grid[-1] >= 65 else np.nan
    # log-point changes of the cubic between fixed ages (less sensitive to the sparse youngest ages)
    for a0, a1 in [(25, 50), (50, 60), (60, 65)]:
        ok = grid[0] <= a0 and grid[-1] >= a1
        out[f"d_{a0}_{a1}"] = float(poly_eval(c3, [a1])[0] - poly_eval(c3, [a0])[0]) if ok else np.nan
    return out


def _pairs(S, resid, unit, time, max_d):
    D = pd.DataFrame({"unit": S[unit].to_numpy(), "t": S[time].to_numpy(), "u": np.asarray(resid, float)})
    m = D.merge(D, on="unit", suffixes=("", "_f"))
    m["d"] = m["t_f"] - m["t"]
    m = m[(m["d"] >= 1) & (m["d"] <= max_d)]
    return pd.DataFrame({"unit": m["unit"].to_numpy(), "d": m["d"].to_numpy(), "t": m["t"].to_numpy(),
                         "r": (m["u_f"] - m["u"]).to_numpy()})


def _ols_d(d, v):
    Z = np.column_stack([np.ones(len(d)), d])
    c, *_ = np.linalg.lstsq(Z, v, rcond=None)
    return c


def cs_variances(S, resid, unit="unit", time="year", max_d=22, min_pairs=30, n_boot=200, seed=0, min_lags=3):
    """Carroll-Samwick shock variances from residual log income.

    resid: u = log y - f(age, Z) (fixed effect left in; it cancels in r_d). Var(r_d) is the sample variance at
    lag d (mean of r_d removed, as CGM). Returns dict with s2_perm, s2_trans (22-point-style OLS on lags with
    at least `min_pairs` pairs), bootstrap SEs (Poisson weights by unit, residuals held fixed), the same with
    r_d demeaned by (d, start year) to strip aggregate shocks (`_yd`), and with d >= 3 only (`_dge3`); plus
    the per-lag table.
    """
    P = _pairs(S, resid, unit, time, max_d)
    if P.empty:
        return None, None
    P["r_yd"] = P["r"] - P.groupby(["d", "t"])["r"].transform("mean")
    V = P.groupby("d").agg(n_pairs=("r", "size"), var=("r", "var"), mean=("r", "mean"), var_yd=("r_yd", "var"))
    V = V[V["n_pairs"] >= min_pairs].reset_index()
    if len(V) < min_lags:
        return None, V
    keep = P["d"].isin(V["d"])
    P = P[keep]
    out = {}
    for tag, col in [("", "var"), ("_yd", "var_yd")]:
        c = _ols_d(V["d"].to_numpy(float), V[col].to_numpy())
        out[f"s2_perm{tag}"], out[f"s2_trans{tag}"] = c[1], c[0] / 2
    V3 = V[V["d"] >= 3]
    if len(V3) >= 3:
        c = _ols_d(V3["d"].to_numpy(float), V3["var"].to_numpy())
        out["s2_perm_dge3"], out["s2_trans_dge3"] = c[1], c[0] / 2
    out["max_d_used"] = int(V["d"].max())
    out["n_lags"] = len(V)
    out["n_pairs"] = int(V["n_pairs"].sum())
    # bootstrap: per (unit, d) sufficient statistics, Poisson(1) unit weights
    uid, uniq = pd.factorize(P["unit"])
    dvals = V["d"].to_numpy()
    didx = pd.Index(dvals).get_indexer(P["d"])
    key = uid * len(dvals) + didx
    agg = pd.DataFrame({"key": key, "r": P["r"].to_numpy()}).groupby("key")["r"].agg(["size", "sum", lambda s: (s * s).sum()])
    agg.columns = ["n", "s1", "s2"]
    k = agg.index.to_numpy()
    ku, kd = k // len(dvals), k % len(dvals)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        w = rng.poisson(1.0, len(uniq))[ku]
        n = np.bincount(kd, w * agg["n"].to_numpy(), len(dvals))
        s1 = np.bincount(kd, w * agg["s1"].to_numpy(), len(dvals))
        s2 = np.bincount(kd, w * agg["s2"].to_numpy(), len(dvals))
        var = (s2 - s1 ** 2 / n) / (n - 1)
        c = _ols_d(dvals.astype(float), var)
        draws.append((c[1], c[0] / 2))
    draws = np.array(draws)
    out["s2_perm_se"], out["s2_trans_se"] = draws.std(axis=0, ddof=1)
    return out, V
