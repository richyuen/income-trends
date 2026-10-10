"""Replicate the labor income process of Cocco, Gomes and Maenhout (2005, RFS), Section 2.1 and Appendix B.

Steps (each written to cgm/output/):
  1. Sample: PSID SRC male heads, survey years 1970-1992, ages 20-65 (22-65 for college), excluding retired
     (1970-1975: retired or disabled), housewives and students; positive CGM income; a new unit whenever the
     head's education group changes.
  2. Fixed-effects regression of log real income (1992 dollars, CPI-U) on age dummies, marital status and
     household composition (members besides head and spouse), by education group -> Table 1.
  3. Third- and fifth-order polynomials fitted to the age dummies -> Table 2; replacement rate -> Table 2.
  4. Carroll-Samwick variance decomposition of the residual log income -> Table 3 (shock variances).
  5. Correlation of aggregate permanent shocks with excess stock returns -> Table 3 (rho).

Usage: python3 -I cgm/scripts/replicate.py [PANEL_DIR]
PANEL_DIR defaults to /mnt/project-files/psid (the private PSID panel; never committed).
Only aggregate tables are written to the repo.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "cgm", "output")
PANEL = sys.argv[1] if len(sys.argv) > 1 else "/mnt/project-files/psid"

GROUPS = {1: "no_high_school", 2: "high_school", 3: "college"}
MIN_AGE = {1: 20, 2: 20, 3: 22}
MAX_AGE = 65
YEARS = (1970, 1992)          # survey years; income years 1969-1991
BASE_YEAR = 1992              # CPI base year for real income
MAX_D = 22

# Published values (CGM 2005, Tables 1-3), for the comparison tables.
CGM_T1 = {
    "no_high_school": dict(famsize=-0.0176, famsize_t=-3.12, married=0.4008, married_t=18.48, const=2.6275,
                           n=1104, Tbar=8.58, s2e=0.1583, r2_within=0.0648, F=12.27),
    "high_school": dict(famsize=-0.0236, famsize_t=-7.42, married=0.4437, married_t=43.21, const=2.7004,
                        n=2816, Tbar=9.57, s2e=0.1161, r2_within=0.1395, F=83.10),
    "college": dict(famsize=-0.0228, famsize_t=-4.63, married=0.4831, married_t=30.50, const=2.3831,
                    n=1110, Tbar=11.06, s2e=0.1189, r2_within=0.2609, F=87.23),
}
CGM_T2 = {  # third-order polynomial in age, age^2/10, age^3/100; replacement rate
    "no_high_school": dict(c0=-2.1361, c1=0.1684, c2=-0.0353, c3=0.0023, repl=0.88983),
    "high_school": dict(c0=-2.1700, c1=0.1682, c2=-0.0323, c3=0.0020, repl=0.68212),
    "college": dict(c0=-4.3148, c1=0.3194, c2=-0.0577, c3=0.0033, repl=0.938873),
}
CGM_T3 = {
    "no_high_school": dict(s2_trans=0.1056, s2_trans_t=13.260, s2_perm=0.0105, s2_perm_t=9.909, rho=-0.0143, rho_t=-0.217),
    "high_school": dict(s2_trans=0.0738, s2_trans_t=21.962, s2_perm=0.0106, s2_perm_t=24.258, rho=0.0058, rho_t=0.143),
    "college": dict(s2_trans=0.0584, s2_trans_t=13.089, s2_perm=0.0169, s2_perm_t=29.196, rho=-0.0175, rho_t=-0.540),
}


def load():
    F = pd.read_parquet(os.path.join(PANEL, "psid_family_year.parquet"))
    cpi = pd.read_csv(os.path.join(ROOT, "cpi", "data", "price_indexes_annual.csv"))
    cpi = cpi.set_index("year")["cpi_u"]
    F["defl"] = F["income_year"].map(cpi / cpi.loc[BASE_YEAR])
    F["y_real"] = F["cgm_inc"] / F["defl"] / 1000.0          # thousands of 1992 dollars
    F["hhcomp"] = (F["fu_size"] - 1 - F["married"]).clip(lower=0)
    F["person"] = F["pid68_h"].astype("int64") * 1000 + F["pn_h"].astype("int64")
    return F


def cgm_sample(F):
    """The estimation sample. Returns the sample and the count of nonpositive-income observations dropped."""
    S = F[(F["sample"] == "SRC") & (F["sex_h"] == 1) & F["year"].between(*YEARS)
          & F["age_h"].between(20, MAX_AGE) & ~F["emp_h8"].isin([4, 6, 7]) & F["educ3_h"].notna()
          & F["cgm_inc"].notna()].copy()
    S = S[S["age_h"] >= S["educ3_h"].map(MIN_AGE)]
    n_all, n_nonpos = len(S), int((S["cgm_inc"] <= 0).sum())
    S = S[S["cgm_inc"] > 0].copy()
    S["educ3_h"] = S["educ3_h"].astype(int)
    S["unit"] = S["person"] * 10 + S["educ3_h"]
    S["logy"] = np.log(S["y_real"])
    S["age_h"] = S["age_h"].astype(int)
    return S, n_all, n_nonpos


def within(x, g):
    return x - x.groupby(g).transform("mean")


def fe_regression(S, min_age):
    """Within estimator: log y on age dummies (youngest age omitted), married, household composition."""
    ages = np.arange(min_age + 1, MAX_AGE + 1)
    X = pd.DataFrame({f"age{a}": (S["age_h"] == a).astype(float) for a in ages}, index=S.index)
    X["married"] = S["married"].astype(float)
    X["hhcomp"] = S["hhcomp"].astype(float)
    y = S["logy"]
    Xd = X.apply(lambda c: within(c, S["unit"]))
    yd = within(y, S["unit"])
    b, *_ = np.linalg.lstsq(Xd.to_numpy(), yd.to_numpy(), rcond=None)
    e = yd.to_numpy() - Xd.to_numpy() @ b
    N, k, n = len(S), X.shape[1], S["unit"].nunique()
    dof = N - n - k
    s2 = e @ e / dof
    XtX_inv = np.linalg.inv(Xd.to_numpy().T @ Xd.to_numpy())
    se = np.sqrt(np.diag(XtX_inv) * s2)
    # cluster-robust (by unit) standard errors, for reference
    Xe = Xd.to_numpy() * e[:, None]
    G = pd.DataFrame(Xe).groupby(S["unit"].to_numpy()).sum().to_numpy()
    se_cl = np.sqrt(np.diag(XtX_inv @ (G.T @ G) @ XtX_inv) * (n / (n - 1)) * ((N - 1) / (N - k)))
    tss = yd.to_numpy() @ yd.to_numpy()
    r2w = 1 - (e @ e) / tss
    F_stat = (r2w / k) / ((1 - r2w) / dof)
    const = y.mean() - X.mean().to_numpy() @ b       # Stata xtreg, fe convention
    coef = pd.DataFrame({"coef": b, "se": se, "t": b / se, "se_cluster": se_cl}, index=X.columns)
    # fitted deterministic part f(t, Z) without the fixed effect, and the unit effects
    fhat = X.to_numpy() @ b
    alpha = (y - fhat).groupby(S["unit"]).transform("mean") - const
    stats = dict(N=N, n=n, Tbar=N / n, s2e=s2, r2_within=r2w, F=F_stat, const=const,
                 sigma_alpha2=float(alpha.groupby(S["unit"]).first().var()))
    return coef, stats, pd.Series(fhat, index=S.index)


def age_profile(coef, min_age):
    d = {min_age: 0.0}
    d.update({int(i[3:]): v for i, v in coef["coef"].items() if i.startswith("age")})
    return pd.Series(d).sort_index()


def poly_fit(prof, order):
    a = prof.index.to_numpy(float)
    cols = [np.ones_like(a)] + [a ** p / 10 ** (p - 1) for p in range(1, order + 1)]
    Z = np.column_stack(cols)
    c, *_ = np.linalg.lstsq(Z, prof.to_numpy(), rcond=None)
    return c, Z @ c


def poly_eval(c, ages):
    a = np.asarray(ages, float)
    return sum(c[p] * a ** p / 10 ** max(p - 1, 0) for p in range(len(c)))


def replacement_rate(F, educ):
    """Mean CGM income of retirees / mean CGM income in the last working year before retirement.

    Retirement = first SRC male-head wave j reported retired (emp_h8 == 4; 1970-1975 code 4 also covers the
    disabled) at age 50+, with the previous wave (at most two years earlier) not retired. Last working year =
    income of wave j-1; retired income = the head's mean over waves j+1, j+2, ... while still retired (each
    retiree counts once). The education group is the
    head's person-level modal group. Retired years are all later waves while still retired, through the same
    survey window and also through 2023 (reported separately).
    """
    R = F[(F["sample"] == "SRC") & (F["sex_h"] == 1) & F["cgm_inc"].notna()].copy()
    R["educ_p"] = R["educ3_h_p"].fillna(R["educ3_h"])
    R = R.sort_values(["person", "year"])
    R["ret"] = R["emp_h8"] == 4
    out = {}
    for window in [YEARS, (1970, 2023)]:
        W = R[R["year"].between(*window)]
        last_work, ret_inc = [], []
        for pid, g in W[W["educ_p"] == educ].groupby("person"):
            yrs, ret, y = g["year"].to_numpy(), g["ret"].to_numpy(), g["y_real"].to_numpy()
            age = g["age_h"].to_numpy()
            for j in range(1, len(g)):
                gap = yrs[j] - yrs[j - 1]
                if ret[j] and not ret[j - 1] and gap <= 2 and age[j] >= 50 and y[j - 1] > 0:
                    # income is for the year before the interview: wave j still holds much of the last working
                    # year, so retired income starts at wave j+1 (the first income year fully in retirement)
                    k, inc = j + 1, []
                    while k < len(g) and ret[k]:
                        inc.append(y[k]); k += 1
                    if inc:
                        last_work.append(y[j - 1]); ret_inc.append(np.mean(inc))
                    break
        out[window] = dict(n_retirees=len(last_work), n_retired_obs=len(ret_inc),
                           mean_last_work=float(np.mean(last_work)), mean_retired=float(np.mean(ret_inc)),
                           repl=float(np.mean(ret_inc) / np.mean(last_work)))
    # Cross-sectional version: retired heads aged 65-75 vs working (sample-eligible) heads aged 60-65,
    # survey years 1970-1992, both by the head's education group in that wave.
    X = R[R["year"].between(*YEARS) & (R["educ3_h"] == educ) & (R["cgm_inc"] > 0)]
    ret = X[X["ret"] & X["age_h"].between(65, 75)]["y_real"]
    wrk = X[~X["emp_h8"].isin([4, 6, 7]) & X["age_h"].between(60, 65)]["y_real"]
    out["xs"] = dict(repl=float(ret.mean() / wrk.mean()), n_ret=len(ret), n_wrk=len(wrk))
    return out


def variance_decomposition(S, resid):
    """Carroll-Samwick (1997): Var(r_d) = d*s2_perm + 2*s2_trans, r_d = u_{t+d} - u_t, d = 1..22.

    Two estimators are reported:
      'cs_ols'   OLS of the 22 sample variances on d and a constant (Appendix B, Eq. 19);
      'pooled'   OLS of the squared demeaned differences on d and a constant over all pairs, with SEs
                 clustered by unit (uses every pair; the t-ratios are of this kind).
    """
    D = S[["unit", "year"]].assign(u=resid.to_numpy())
    rows = []
    pairs = []
    for d in range(1, MAX_D + 1):
        m = D.merge(D.assign(year=D["year"] - d), on=["unit", "year"], suffixes=("", "_f"))
        r = m["u_f"] - m["u"]
        rows.append(dict(d=d, n_pairs=len(r), var=float(r.var()), mean=float(r.mean())))
        pairs.append(pd.DataFrame({"unit": m["unit"], "d": d, "r2": (r - r.mean()) ** 2}))
    V = pd.DataFrame(rows)
    V = V[V["n_pairs"] >= 30]                     # sub-windows have fewer lags
    Z = np.column_stack([np.ones(len(V)), V["d"]])
    c, *_ = np.linalg.lstsq(Z, V["var"].to_numpy(), rcond=None)
    e = V["var"].to_numpy() - Z @ c
    s2 = e @ e / (len(V) - 2)
    se = np.sqrt(np.diag(np.linalg.inv(Z.T @ Z)) * s2)
    cs = dict(s2_perm=c[1], s2_perm_t=c[1] / se[1], s2_trans=c[0] / 2, s2_trans_t=c[0] / se[0])
    P = pd.concat(pairs, ignore_index=True)
    Zp = np.column_stack([np.ones(len(P)), P["d"]])
    cp, *_ = np.linalg.lstsq(Zp, P["r2"].to_numpy(), rcond=None)
    ep = P["r2"].to_numpy() - Zp @ cp
    ZZi = np.linalg.inv(Zp.T @ Zp)
    G = pd.DataFrame(Zp * ep[:, None]).groupby(P["unit"].to_numpy()).sum().to_numpy()
    sep = np.sqrt(np.diag(ZZi @ (G.T @ G) @ ZZi))
    pooled = dict(s2_perm=cp[1], s2_perm_t=cp[1] / sep[1], s2_trans=cp[0] / 2, s2_trans_t=cp[0] / sep[0])
    # robustness: drop d=1,2 (MA(1) transitory or measurement error at short lags)
    V3 = V[V["d"] >= 3]
    c3, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(V3)), V3["d"]]), V3["var"].to_numpy(), rcond=None)
    d3 = dict(s2_perm=c3[1], s2_trans=c3[0] / 2)
    return V, cs, pooled, d3


def stock_correlation(S, resid):
    """Aggregate component of permanent shocks: cross-sectional mean of r_1 by year, regressed on demeaned
    excess market returns (Fama-French Mkt-RF, CRSP value-weighted; CGM used the NYSE VW minus T-bill).
    The return is that of the income year (labor income is reported for the calendar year before the survey).
    Also reported: the next year's return (CGM's Eq. 22 uses R_{t+1} in their own timing)."""
    D = S[["unit", "year", "income_year"]].assign(u=resid.to_numpy())
    m = D.merge(D.assign(year=D["year"] - 1), on=["unit", "year"], suffixes=("", "_f"))
    m["r1"] = m["u_f"] - m["u"]
    m["iy"] = m["income_year"] + 1                        # income year of the later observation
    xi = m.groupby("iy")["r1"].mean()
    ff = pd.read_csv(os.path.join(ROOT, "cgm", "data", "ff_market_annual.csv")).set_index("year")["mkt_rf"] / 100
    out = {}
    for lag, name in [(0, "same_year"), (1, "next_year")]:
        ret = ff.reindex(xi.index + lag).to_numpy()
        x = ret - ret.mean()
        Z = np.column_stack([np.ones(len(x)), x])
        c, *_ = np.linalg.lstsq(Z, xi.to_numpy(), rcond=None)
        e = xi.to_numpy() - Z @ c
        se = np.sqrt(np.diag(np.linalg.inv(Z.T @ Z)) * (e @ e) / (len(x) - 2))
        out[name] = dict(beta=c[1], beta_t=c[1] / se[1], rho=float(np.corrcoef(xi.to_numpy(), ret)[0, 1]),
                         n_years=len(x))
    return out


def sensitivity(F, S):
    """Shock variances (22-point Carroll-Samwick OLS) under alternative samples."""
    cases = {
        "baseline": S,
        "drop_real_income_below_2k": S[S["y_real"] >= 2.0],
        "trim_1pct_resid_tails": None,                       # handled below (needs residuals)
        "income_years_1969_1980": S[S["year"] <= 1981],
        "income_years_1981_1991": S[S["year"] >= 1982],
        "unit_is_person_modal_educ": None,
    }
    rows = []
    for case, base in cases.items():
        for e, name in GROUPS.items():
            if case == "unit_is_person_modal_educ":
                G = S[S["educ3_h_p"] == e].copy(); G["unit"] = G["person"]
            else:
                G = (S if base is None else base)
                G = G[G["educ3_h"] == e]
            coef, st, fhat = fe_regression(G, MIN_AGE[e])
            resid = G["logy"] - fhat
            if case == "trim_1pct_resid_tails":
                dev = resid - resid.groupby(G["unit"]).transform("mean")
                keep = dev.between(dev.quantile(0.005), dev.quantile(0.995))
                G = G[keep]; coef, st, fhat = fe_regression(G, MIN_AGE[e]); resid = G["logy"] - fhat
            V, cs, pooled, d3 = variance_decomposition(G, resid)
            rows.append(dict(case=case, group=name, obs=len(G), s2e=st["s2e"], s2_trans=cs["s2_trans"],
                             s2_perm=cs["s2_perm"], cgm_s2_trans=CGM_T3[name]["s2_trans"],
                             cgm_s2_perm=CGM_T3[name]["s2_perm"]))
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    F = load()
    S, n_all, n_nonpos = cgm_sample(F)
    print(f"sample: {len(S)} obs; nonpositive income dropped {n_nonpos} ({n_nonpos / n_all:.3%}; CGM 326, 0.495%)")

    t1, t2, t3, prof_rows, var_rows, coef_rows = [], [], [], [], [], []
    for e, name in GROUPS.items():
        G = S[S["educ3_h"] == e]
        coef, st, fhat = fe_regression(G, MIN_AGE[e])
        coef_rows.append(coef.reset_index(names="var").assign(group=name))
        k = CGM_T1[name]
        t1.append(dict(group=name,
                       famsize=coef.loc["hhcomp", "coef"], famsize_t=coef.loc["hhcomp", "t"],
                       famsize_t_cluster=coef.loc["hhcomp", "coef"] / coef.loc["hhcomp", "se_cluster"],
                       married=coef.loc["married", "coef"], married_t=coef.loc["married", "t"],
                       married_t_cluster=coef.loc["married", "coef"] / coef.loc["married", "se_cluster"],
                       const=st["const"], n=st["n"], obs=st["N"], Tbar=st["Tbar"], s2e=st["s2e"],
                       r2_within=st["r2_within"], F=st["F"], sigma_alpha2=st["sigma_alpha2"],
                       **{f"cgm_{a}": b for a, b in k.items()}))

        prof = age_profile(coef, MIN_AGE[e])
        c3, fit3 = poly_fit(prof, 3)
        c5, fit5 = poly_fit(prof, 5)
        rr = replacement_rate(F, e)
        ck = CGM_T2[name]
        cgm_curve = poly_eval([ck["c0"], ck["c1"], ck["c2"], ck["c3"]], prof.index)
        for a, v, f3, f5, fc in zip(prof.index, prof.to_numpy(), fit3, fit5, cgm_curve):
            prof_rows.append(dict(group=name, age=a, age_dummy=v, poly3=f3, poly5=f5, cgm_poly3=fc,
                                  level_k1992=np.exp(st["const"] + v + coef.loc["married", "coef"] * G["married"].mean()
                                                     + coef.loc["hhcomp", "coef"] * G["hhcomp"].mean())))
        t2.append(dict(group=name, **{f"p3_c{i}": c for i, c in enumerate(c3)}, **{f"p5_c{i}": c for i, c in enumerate(c5)},
                       repl_1970_1992=rr[YEARS]["repl"], repl_n_retirees=rr[YEARS]["n_retirees"],
                       repl_mean_last_work=rr[YEARS]["mean_last_work"], repl_mean_retired=rr[YEARS]["mean_retired"],
                       repl_1970_2023=rr[(1970, 2023)]["repl"], repl_n_ret_1970_2023=rr[(1970, 2023)]["n_retirees"],
                       repl_xs_ret65_75_vs_work60_65=rr["xs"]["repl"], repl_xs_n_ret=rr["xs"]["n_ret"],
                       peak_age_p3=int(prof.index[np.argmax(fit3)]),
                       growth_to_peak_p3=float(np.exp(fit3.max() - fit3[0])),
                       cgm_peak_age=int(prof.index[np.argmax(cgm_curve)]),
                       cgm_growth_to_peak=float(np.exp(cgm_curve.max() - cgm_curve[0])),
                       **{f"cgm_{a}": b for a, b in ck.items()}))

        resid = G["logy"] - fhat
        V, cs, pooled, d3 = variance_decomposition(G, resid)
        var_rows.append(V.assign(group=name))
        rho = stock_correlation(G, resid)
        t3.append(dict(group=name,
                       s2_trans=cs["s2_trans"], s2_trans_t=cs["s2_trans_t"], s2_perm=cs["s2_perm"], s2_perm_t=cs["s2_perm_t"],
                       pooled_s2_trans=pooled["s2_trans"], pooled_s2_trans_t=pooled["s2_trans_t"],
                       pooled_s2_perm=pooled["s2_perm"], pooled_s2_perm_t=pooled["s2_perm_t"],
                       dge3_s2_trans=d3["s2_trans"], dge3_s2_perm=d3["s2_perm"],
                       rho=rho["same_year"]["rho"], rho_beta=rho["same_year"]["beta"], rho_beta_t=rho["same_year"]["beta_t"],
                       rho_next=rho["next_year"]["rho"], rho_next_beta_t=rho["next_year"]["beta_t"],
                       rho_n_years=rho["same_year"]["n_years"],
                       **{f"cgm_{a}": b for a, b in CGM_T3[name].items()}))

    sens = sensitivity(F, S)
    sens.round(4).to_csv(os.path.join(OUT, "sensitivity_variances.csv"), index=False)
    pd.DataFrame(t1).round(4).to_csv(os.path.join(OUT, "table1_fixed_effects.csv"), index=False)
    pd.DataFrame(t2).round(6).to_csv(os.path.join(OUT, "table2_age_polynomial.csv"), index=False)
    pd.DataFrame(t3).round(4).to_csv(os.path.join(OUT, "table3_variances.csv"), index=False)
    pd.DataFrame(prof_rows).round(5).to_csv(os.path.join(OUT, "age_profiles.csv"), index=False)
    pd.concat(var_rows).round(5).to_csv(os.path.join(OUT, "var_by_lag.csv"), index=False)
    pd.concat(coef_rows).round(5).to_csv(os.path.join(OUT, "fe_coefficients.csv"), index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)
    print("\n== sensitivity_variances\n", sens.round(4).to_string(index=False))
    for f in ["table1_fixed_effects", "table2_age_polynomial", "table3_variances"]:
        print(f"\n== {f}\n", pd.read_csv(os.path.join(OUT, f + ".csv")).set_index("group").T)


if __name__ == "__main__":
    main()
