"""Step 3, SIPP and CPS ASEC: the income process from the Census surveys, to set beside the PSID estimates.

Both surveys measure each person's own annual earnings, not CGM's household income, so the PSID comparison is
`head_earn` in psid_extend.py (the male head's own labor income, no household controls). Common sample: men aged
20-65 (22-65 with a college degree), real earnings of at least $2,000 in 1992 dollars (CPI-U), earnings not imputed.
Education: no high school diploma / high school (incl. some college) / college degree.

SIPP (panels 1996, 2001, 2004, 2008 = old design, income years 1995-2013; 2014-2024 panels = new design, 2013-2024):
  full-year person-years, no imputed month (imp_share 0, not Type-Z), no top-coded month. Within each era (panels
  never pooled across the 2013 design break): Carroll-Samwick variances with lags up to 4 years on fixed-effects
  residuals (unit = panel x person x education; unweighted, like the PSID). With 2-4 years per person the
  fixed-effects age profile is not identified well, so the reported profile is the synthetic-cohort one (as for the
  CPS, weighted by the person weight of the last month). Cuts: all, education, industry (person's modal sector of
  the main job within the panel); also each panel separately.
CPS ASEC (income years 1987-2025, cross sections, plus one-year matches 1987-92 and 1995-2013):
  - profile: synthetic-cohort age profile, the weighted mean log earnings of (birth year x age) cells regressed on age
    dummies and birth-year dummies (what the PSID fixed-effects profile measures: growth along a cohort's life);
  - permanent variance (Deaton-Paxson): within-cohort cross-sectional variance of log earnings regressed on age
    (ages 25-60) and birth-year dummies; the age slope is s2_perm;
  - Var(D1): variance of the one-year change in log earnings of matched men (demeaned by year and 5-year age group),
    = s2_perm + 2*s2_trans under the CGM model, so s2_trans = (Var(D1) - s2_perm) / 2.
  Weighted by MARSUPWT (the year-t weight for matches). 2014 uses the redesigned-questionnaire file (3/8 sample),
  2017-2018 the production files.
Periods (income years) as in the PSID: p2 1981-1992 (CPS from 1987), p3 1993-2006, p4 2007-2022 (CPS and SIPP to
2025/2024; labelled with the years used), and for the CPS all years, 1987-2025. Like CGM's, these profiles carry the
period's aggregate earnings growth (no year effects), so a short window with a recession or falling real wages bends
them: the CPS p2 window (1987-1992, six years) is the extreme case.

Usage: python3 -I extend/scripts/census_extend.py   (about 3 minutes). Writes extend/output/{sipp,cps}_*.csv.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import incproc as ip  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "extend", "output")
EDUC = {1: "no_high_school", 2: "high_school", 3: "college"}
MIN_AGE = {1: 20, 2: 20, 3: 22}
FLOOR = 2.0
PERIODS = {"p2": (1981, 1992), "p3": (1993, 2006), "p4": (2007, 2025), "full": (1969, 2025)}
MIN_UNITS = 40


def cpi_factor():
    cpi = pd.read_csv(os.path.join(ROOT, "cpi", "data", "price_indexes_annual.csv")).set_index("year")["cpi_u"]
    return cpi / cpi.loc[1992]


# ---------------------------------------------------------------- SIPP
def sipp_load():
    defl = cpi_factor()
    cols = ["panel", "design", "pid", "year", "earn_tot", "full_year", "imp_share", "typez_months", "tc_any", "age",
            "sex", "educ4", "ms", "famsize", "main_ind", "main_jobkey", "ind_vintage", "byear", "wgt_last"]
    S = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(os.path.join(ROOT, "sipp", "data", "sipp_py_*.parquet")))])
    S = S[(S["sex"] == 1) & S["full_year"] & (S["imp_share"].fillna(0) == 0) & (S["typez_months"] == 0) & ~S["tc_any"]
          & S["age"].between(20, 65) & S["educ4"].notna()].copy()
    S["educ3"] = S["educ4"].map({1: 1, 2: 2, 3: 2, 4: 3}).astype(int)
    S = S[S["age"] >= S["educ3"].map(MIN_AGE)]
    S["y"] = S["earn_tot"] / S["year"].map(defl) / 1000
    S = S[S["y"] >= FLOOR].copy()
    S["logy"] = np.log(S["y"])
    S["age"] = S["age"].astype(int)
    S["era"] = np.where(S["design"] == "old", "old_1995_2013", "new_2013_2024")
    S["person"] = S["panel"].astype(str) + "_" + S["pid"]
    S["unit"] = S["person"] + "_" + S["educ3"].astype(str)
    code = pd.to_numeric(S["main_ind"], errors="coerce")
    code[(S["design"] == "old") & (S["main_jobkey"] >= 100)] = np.nan       # old-panel businesses: 2-digit recode
    S["sector"] = ip.industry_sector(code, (S["ind_vintage"] != "Census 1990 IND").to_numpy())
    mode = (S.dropna(subset=["sector"]).groupby(["person", "sector"]).size().rename("n").reset_index()
            .sort_values(["person", "n"]).groupby("person").tail(1).set_index("person")["sector"])
    S["g_all"] = "all"
    S["g_education"] = S["educ3"].map(EDUC)
    S["g_industry"] = S["person"].map(mode).map(ip.SECTORS)
    return S


def sipp_run(S):
    rows, profs, lags = [], [], []
    plan = [("era", e, ["all", "education", "industry"]) for e in S["era"].unique()]
    plan += [("panel", str(p), ["all", "education"]) for p in sorted(S["panel"].unique())]
    for kind, val, cuts in plan:
        W = S[S["era"] == val] if kind == "era" else S[S["panel"].astype(str) == val]
        for cut in cuts:
            for grp, G in W.dropna(subset=[f"g_{cut}"]).groupby(f"g_{cut}"):
                if G["unit"].nunique() < MIN_UNITS or G["year"].nunique() < 3:
                    continue
                coef, st, fhat, _ = ip.fe_regression(G, controls=())
                cs, V = ip.cs_variances(G, G["logy"] - fhat, time="year", max_d=4, min_lags=2)
                key = dict(source="sipp", measure="person_earn", period=f"{kind}_{val}",
                           years=f"{G['year'].min()}-{G['year'].max()}", cut=cut, group=grp)
                row = dict(key, **st, **(cs or {}))
                if kind == "era":                 # single panels are too thin for (birth year x age) cells
                    prof, _ = synthetic_profile(G, time="year", w="wgt_last", min_cell=10)
                    c3, fit3 = ip.poly_fit(prof, 3)
                    row.update({f"p3_c{i}": c for i, c in enumerate(c3)}, **ip.profile_summary(c3, prof))
                    profs.append(pd.DataFrame(dict(key, age=prof.index, age_dummy=prof.to_numpy(), cubic=fit3.to_numpy(),
                                                   profile="synthetic_cohort")))
                rows.append(row)
                if V is not None:
                    lags.append(V.assign(**key))
        print(f"  sipp {kind} {val} done", flush=True)
    return rows, profs, lags


# ---------------------------------------------------------------- CPS ASEC
CPS_COLS = ["asec_year", "income_year", "file", "ph_seq", "pppos", "age", "sex", "a_hga", "a_hgc", "pearnval",
            "i_ernval", "i_wsval", "i_seval", "i_frmval", "marsupwt"]


def cps_educ3(c):
    hga = c["a_hga"]
    if c["asec_year"].iloc[0] <= 1991:      # grade attended 0-18 with a completed flag (1 = yes)
        yrs = hga - (c["a_hgc"] != 1).astype(int)
        return np.select([yrs >= 16, yrs >= 12], [3, 2], 1)
    return np.select([hga >= 43, hga >= 39], [3, 2], 1)   # 1992+: 39 HS diploma, 43 bachelor's


def cps_load():
    defl = cpi_factor()
    files = sorted(glob.glob(os.path.join(ROOT, "cps", "data", "asec_*_*.parquet")))
    files = [f for f in files if "links" not in f and "traditional" not in f and "research" not in f and "bridge" not in f]
    out = []
    for f in files:
        have = set(pq.read_schema(f).names)
        c = pd.read_parquet(f, columns=[x for x in CPS_COLS if x in have])
        c = c[(c["sex"] == 1) & c["age"].between(20, 65)].copy()
        c["educ3"] = cps_educ3(c)
        c["imputed"] = (c[["i_ernval", "i_wsval", "i_seval", "i_frmval"]].fillna(0) != 0).any(axis=1)
        c["y"] = c["pearnval"] / c["income_year"].map(defl) / 1000
        out.append(c.drop(columns=["a_hga", "a_hgc", "i_ernval", "i_wsval", "i_seval", "i_frmval"], errors="ignore"))
    C = pd.concat(out, ignore_index=True)
    C = C[C["age"] >= C["educ3"].map(MIN_AGE)]
    C["byear"] = C["income_year"] - C["age"]
    return C


def wmean_var(g, col, w="marsupwt"):
    x, ww = g[col].to_numpy(), g[w].to_numpy()
    m = np.average(x, weights=ww)
    return pd.Series(dict(mean=m, var=np.average((x - m) ** 2, weights=ww), n=len(x), w=ww.sum()))


def dummies_ols(df, yname, cat_cols, lin_col=None, w=None):
    X = pd.concat([pd.get_dummies(df[c].astype(str), prefix=c, drop_first=(i > 0)) for i, c in enumerate(cat_cols)], axis=1).astype(float)
    if lin_col:
        X[lin_col] = df[lin_col].astype(float)
    sw = np.sqrt(df[w].to_numpy()) if w else np.ones(len(df))
    b, *_ = np.linalg.lstsq(X.to_numpy() * sw[:, None], df[yname].to_numpy() * sw, rcond=None)
    return pd.Series(b, index=X.columns)


def synthetic_profile(G, time="income_year", w="marsupwt", min_cell=20):
    """Synthetic-cohort age profile: weighted mean log earnings of (birth year x age) cells regressed on age dummies
    and birth-year dummies (cell weights = summed person weights). Youngest age = 0. Also returns the cells."""
    G = G[G[w] > 0].assign(byear_=lambda d: d[time] - d["age"])
    cells = G.groupby(["byear_", "age"]).apply(lambda g: wmean_var(g, "logy", w), include_groups=False).reset_index()
    cells = cells[cells["n"] >= min_cell]
    b = dummies_ols(cells, "mean", ["age", "byear_"], w="w")
    ages = sorted(cells["age"].unique())
    prof = pd.Series([0.0] + [b[f"age_{a}"] - b[f"age_{ages[0]}"] for a in ages[1:]], index=ages)
    return prof, cells


def cps_run(C):
    links = pd.read_parquet(os.path.join(ROOT, "cps", "data", "asec_links.parquet"))
    ok = C[(C["y"] >= FLOOR) & ~C["imputed"]].copy()
    ok["logy"] = np.log(ok["y"])
    rows, profs = [], []
    # one-year changes from matched pairs
    a = ok[["asec_year", "file", "ph_seq", "pppos", "logy", "educ3", "age", "marsupwt", "income_year"]]
    # match rates are 42-76% for ASEC 1988-92 and 1996-2014 and under 6% otherwise (cps/output/link_rates.csv)
    L = links[links["asec_year"].between(1988, 1992) | links["asec_year"].between(1996, 2014)].drop(columns=["age_t", "age_t1"])
    M = L.merge(a.rename(columns={"file": "file_t", "ph_seq": "ph_seq_t", "pppos": "pppos_t", "logy": "logy_t",
                                  "educ3": "educ3_t", "age": "age_t", "marsupwt": "marsupwt_t", "income_year": "income_year_t"}),
                on=["asec_year", "file_t", "ph_seq_t", "pppos_t"])
    a1 = a.assign(asec_year=a["asec_year"] - 1)[["asec_year", "file", "ph_seq", "pppos", "logy"]]
    M = M.merge(a1.rename(columns={"file": "file_t1", "ph_seq": "ph_seq_t1", "pppos": "pppos_t1", "logy": "logy_x"}),
                on=["asec_year", "file_t1", "ph_seq_t1", "pppos_t1"])
    M["dly"] = M["logy_x"] - M["logy_t"]
    M["ag5"] = M["age_t"] // 5
    M["dly"] = M["dly"] - M.groupby(["income_year_t", "ag5"])["dly"].transform("mean")
    dyear = (M.assign(g=M["educ3_t"].map(EDUC)).groupby(["income_year_t", "g"])
             .apply(lambda g: wmean_var(g, "dly", "marsupwt_t"), include_groups=False).reset_index())
    dyear_all = M.groupby("income_year_t").apply(lambda g: wmean_var(g, "dly", "marsupwt_t"), include_groups=False).reset_index().assign(g="all")
    dyear = pd.concat([dyear, dyear_all]).rename(columns={"income_year_t": "income_year", "g": "group"})
    dyear[["income_year", "group", "n", "var"]].rename(columns={"var": "var_d1"}).to_csv(
        os.path.join(OUT, "cps_var_d1_by_year.csv"), index=False, float_format="%.6g")

    ok["g_all"] = "all"
    ok["g_education"] = ok["educ3"].map(EDUC)
    for period, (y0, y1) in PERIODS.items():
        W = ok[ok["income_year"].between(y0, y1)]
        for cut in ["all", "education"]:
            for grp, G in W.groupby(f"g_{cut}"):
                prof, cells = synthetic_profile(G)
                c3, fit3 = ip.poly_fit(prof, 3)
                dp = cells[cells["age"].between(25, 60)]
                bd = dummies_ols(dp, "var", ["byear_"], lin_col="age", w="w")
                s2p = float(bd["age"])
                mm = M[M["income_year_t"].between(y0, y1)]
                if cut == "education":
                    mm = mm[mm["educ3_t"].map(EDUC) == grp]
                vd1 = float(wmean_var(mm, "dly", "marsupwt_t")["var"]) if len(mm) > 100 else np.nan
                key = dict(source="cps", measure="person_earn", period=period,
                           years=f"{G['income_year'].min()}-{G['income_year'].max()}", cut=cut, group=grp)
                rows.append(dict(key, n_obs=len(G), n_cells=len(cells), **{f"p3_c{i}": c for i, c in enumerate(c3)},
                                 **ip.profile_summary(c3, prof), s2_perm=s2p, var_d1=vd1, n_pairs=len(mm),
                                 pair_years=f"{int(mm['income_year_t'].min())}-{int(mm['income_year_t'].max()) + 1}" if len(mm) else "",
                                 s2_trans=(vd1 - s2p) / 2))
                profs.append(pd.DataFrame(dict(key, age=prof.index, age_dummy=prof.to_numpy(), cubic=fit3.to_numpy())))
        print(f"  cps {period} done", flush=True)
    # cross-sectional variance of log earnings by year (all men 25-60), for the trend chart
    xs = (ok[ok["age"].between(25, 60)].assign(g=lambda d: d["educ3"].map(EDUC))
          .groupby(["income_year", "g"]).apply(lambda g: wmean_var(g, "logy"), include_groups=False).reset_index())
    xs.rename(columns={"g": "group", "mean": "mean_logy", "var": "var_logy"}).to_csv(
        os.path.join(OUT, "cps_xs_by_year.csv"), index=False, float_format="%.6g")
    return rows, profs


def main():
    os.makedirs(OUT, exist_ok=True)
    S = sipp_load()
    r, p, l = sipp_run(S)
    pd.DataFrame(r).to_csv(os.path.join(OUT, "sipp_estimates.csv"), index=False, float_format="%.6g")
    pd.concat(p).to_csv(os.path.join(OUT, "sipp_profiles.csv"), index=False, float_format="%.6g")
    pd.concat(l).to_csv(os.path.join(OUT, "sipp_var_by_lag.csv"), index=False, float_format="%.6g")
    C = cps_load()
    r, p = cps_run(C)
    pd.DataFrame(r).to_csv(os.path.join(OUT, "cps_estimates.csv"), index=False, float_format="%.6g")
    pd.concat(p).to_csv(os.path.join(OUT, "cps_profiles.csv"), index=False, float_format="%.6g")


if __name__ == "__main__":
    main()
