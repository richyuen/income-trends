"""Step 3, PSID: the CGM (2005) income process by education, industry, income group and birth cohort, by period,
and over rolling windows, 1969-2022 (income years; survey years 1970-2023).

Default sample (Richard, 2026-10-10): CGM's sample (SRC male heads, ages 20-65, 22-65 for college, not retired,
housewife or student) extended to survey 2023, dropping observations with real CGM income under $2,000 (1992
dollars). The full sample (positive income) is the robustness check. The method is CGM's, unchanged: fixed-effects
age profile with marital status and household composition, a cubic fit, and Carroll-Samwick shock variances
(OLS of Var(r_d) on d). Lags d are in calendar years, so the biennial waves after 1997 contribute even lags only.

Cuts (each estimated separately, as CGM do by education):
  all             everyone (units still split by education group, as in CGM)
  education       no high school / high school / college (head's group in the wave)
  industry        7 sectors (incproc.SECTORS), the person's modal sector over his sample years in the period
  income_q        quintile of the person's mean log income relative to his age and year (OLS residual of log
                  income on age and year dummies), over his sample years in the period ("lifetime" ranking)
  income_q_init   quintile of the same residual averaged over the person's first 3 sample years; the profile and
                  variances use only his later years (at least 3), so the ranking years do not enter the variances
  cohort          birth decade (full period only)
Periods (income years): cgm 1969-1991, full 1969-2022, p1 1969-1980, p2 1981-1992, p3 1993-2006, p4 2007-2022;
rolling 12-year windows starting 1969, 1971, ..., 2011 (all and education).
Measures: cgm (CGM household income: head and wife labor income plus transfers; the default), head_earn (head's
own labor income with no household controls, comparable to the SIPP and CPS person earnings in
census_extend.py).

Replacement rate (Richard's default definition, repl_prof65_pens): mean income including pensions of retired SRC
male heads aged 65-75 in the period, over the group's fitted level at 65, exp(const + cubic(65) + married and
household composition at sample means). Retirees are grouped by their education in the wave, or by the person's
industry / income quintile / cohort from his working years (retirees never seen working in the period drop out).

Usage: python3 -I extend/scripts/psid_extend.py [PANEL_DIR]   (about 4 minutes)
Writes aggregate tables only, to extend/output/psid_*.csv.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import incproc as ip  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "extend", "output")
PANEL = sys.argv[1] if len(sys.argv) > 1 else "/mnt/project-files/psid"

EDUC = {1: "no_high_school", 2: "high_school", 3: "college"}
MIN_AGE = {1: 20, 2: 20, 3: 22}
MAX_AGE = 65
BASE_YEAR = 1992
FLOOR = 2.0                       # thousands of 1992 dollars
PERIODS = {"cgm": (1969, 1991), "full": (1969, 2022), "p1": (1969, 1980), "p2": (1981, 1992),
           "p3": (1993, 2006), "p4": (2007, 2022)}
MAX_D = {"cgm": 22, "full": 22}   # other periods and rolling windows: 11
ROLL_LEN, ROLL_STARTS = 12, range(1969, 2012, 2)
MIN_UNITS = 40
# head_earn has no household controls, so its profile is comparable with the SIPP and CPS person profiles
CONTROLS = {"cgm": ("married", "hhcomp"), "head_earn": ()}


def load():
    F = pd.read_parquet(os.path.join(PANEL, "psid_family_year.parquet"))
    cpi = pd.read_csv(os.path.join(ROOT, "cpi", "data", "price_indexes_annual.csv")).set_index("year")["cpi_u"]
    F["defl"] = F["income_year"].map(cpi / cpi.loc[BASE_YEAR])
    F["y_cgm"] = F["cgm_inc"] / F["defl"] / 1000.0
    F["y_head_earn"] = F["labinc_h_cons"] / F["defl"] / 1000.0
    F["hhcomp"] = (F["fu_size"] - 1 - F["married"]).clip(lower=0)
    P = pd.read_parquet(os.path.join(PANEL, "psid_pensions_family_year.parquet"), columns=["year", "fid", "pens_h", "pens_w"])
    F = F.merge(P, on=["year", "fid"], how="left", validate="1:1")
    F["y_pens"] = (F["cgm_inc"] + F["pens_h"] + F["pens_w"].fillna(0)) / F["defl"] / 1000.0
    F["person"] = F["pid68_h"].astype("int64") * 1000 + F["pn_h"].astype("int64")
    four = F["indus_vint"].isin(["census2000_3d", "census2012_4d"]).to_numpy()
    code = F["indus_h"].where(F["indus_vint"] != "census2000_3d", F["indus_h"] * 10)
    F["sector"] = ip.industry_sector(code, four)
    F["cohort"] = (F["yob_h"] // 10 * 10).astype("Int64")
    F["age"] = F["age_h"]
    return F


def base_sample(F, measure, floor):
    ycol = f"y_{measure}"
    S = F[(F["sample"] == "SRC") & (F["sex_h"] == 1) & F["age_h"].between(20, MAX_AGE)
          & ~F["emp_h8"].isin([4, 6, 7]) & F["educ3_h"].notna() & F[ycol].notna() & (F["year"] >= 1970)].copy()
    S = S[S["age_h"] >= S["educ3_h"].map(MIN_AGE)]
    S = S[S[ycol] > 0] if floor is None else S[S[ycol] >= floor]
    S["educ3_h"] = S["educ3_h"].astype(int)
    S["unit"] = S["person"] * 10 + S["educ3_h"]
    S["logy"] = np.log(S[ycol])
    S["age"] = S["age_h"].astype(int)
    return S


def rel_income(S):
    """Residual of log income on age and income-year dummies (pooled OLS), for the income ranking."""
    X = pd.get_dummies(S["age"].astype(str)).join(pd.get_dummies(S["income_year"].astype(str)), rsuffix="_y").astype(float)
    b, *_ = np.linalg.lstsq(X.to_numpy(), S["logy"].to_numpy(), rcond=None)
    return S["logy"] - X.to_numpy() @ b


def person_mode(S, col):
    g = S.dropna(subset=[col]).groupby(["person", col]).agg(n=("year", "size"), last=("year", "max")).reset_index()
    g = g.sort_values(["person", "n", "last"]).groupby("person").tail(1)
    return g.set_index("person")[col]


def quintile(x):
    return pd.qcut(x.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)


def add_groups(W):
    """Group columns for the cuts, computed within the period sample W."""
    W = W.copy()
    W["g_all"] = "all"
    W["g_education"] = W["educ3_h"].map(EDUC)
    sec = person_mode(W, "sector")
    W["g_industry"] = W["person"].map(sec).map(ip.SECTORS)
    W["rel"] = rel_income(W)
    q = quintile(W.groupby("person")["rel"].mean())
    W["g_income_q"] = W["person"].map(q).map(lambda v: f"Q{v}")
    W = W.sort_values(["person", "year"])
    W["seq"] = W.groupby("person").cumcount()
    first3 = W[W["seq"] < 3].groupby("person")["rel"].agg(["mean", "size"])
    later = W[W["seq"] >= 3].groupby("person").size()
    ok = first3.index[(first3["size"] == 3)].intersection(later.index[later >= 3])
    qi = quintile(first3.loc[ok, "mean"])
    W["g_income_q_init"] = np.where(W["seq"] >= 3, W["person"].map(qi).map(lambda v: f"Q{int(v)}" if pd.notna(v) else None), None)
    W["g_cohort"] = W["cohort"].map(lambda c: f"{c}s" if pd.notna(c) else None)
    return W


def retiree_groups(R, W, cut):
    """Group of each retiree row for the replacement rate."""
    if cut == "all":
        return pd.Series("all", index=R.index)
    if cut == "education":
        return R["educ3_h"].map(EDUC)
    if cut == "cohort":
        return R["cohort"].map(lambda c: f"{c}s" if pd.notna(c) else None)
    col = "g_income_q" if cut == "income_q_init" else f"g_{cut}"
    m = W.dropna(subset=[col]).groupby("person")[col].first()
    return R["person"].map(m)


def estimate(G, max_d, controls=("married", "hhcomp")):
    coef, st, fhat, prof = ip.fe_regression(G, controls=controls)
    c3, fit3 = ip.poly_fit(prof, 3)
    row = dict(st, **{f"p3_c{i}": c for i, c in enumerate(c3)}, **ip.profile_summary(c3, prof))
    cs, V = ip.cs_variances(G, G["logy"] - fhat, time="income_year", max_d=max_d)
    if cs:
        row.update(cs)
    # level at 65 (thousands of 1992 dollars) at sample means of the controls, from the cubic
    if prof.index.max() >= 65:
        row["level65_k1992"] = float(np.exp(st["const"] + ip.poly_eval(c3, [65])[0]
                                            + sum(st[c] * st[f"mean_{c}"] for c in controls)))
    return row, prof, fit3, V


def run(F, measure, floor, period, years, cuts, max_d, retirees=True):
    S = base_sample(F, measure, floor)
    W = add_groups(S[S["income_year"].between(*years)])
    R = F[(F["sample"] == "SRC") & (F["sex_h"] == 1) & (F["emp_h8"] == 4) & F["age_h"].between(65, 75)
          & F["income_year"].between(*years) & F["y_pens"].notna()]
    rows, profs, lags = [], [], []
    for cut in cuts:
        col = f"g_{cut}"
        rg = retiree_groups(R, W, cut) if retirees else None
        for grp, G in W.dropna(subset=[col]).groupby(col):
            if G["unit"].nunique() < MIN_UNITS:
                continue
            row, prof, fit3, V = estimate(G, max_d, CONTROLS[measure])
            key = dict(measure=measure, sample="drop_lt2k" if floor else "full", period=period,
                       years=f"{years[0]}-{years[1]}", cut=cut, group=grp)
            if retirees and "level65_k1992" in row:
                y = R.loc[rg == grp, "y_pens"]
                row.update(repl_prof65_pens=y.mean() / row["level65_k1992"], repl_n_ret=len(y),
                           ret_mean_k1992=y.mean())
            rows.append(dict(key, **row))
            profs.append(pd.DataFrame(dict(key, age=prof.index, age_dummy=prof.to_numpy(), cubic=fit3.to_numpy(),
                                           level_k1992=np.exp(row["const"] + prof.to_numpy() + sum(
                                               row[c] * row[f"mean_{c}"] for c in CONTROLS[measure])))))
            if V is not None:
                lags.append(V.assign(**key))
        print(f"  {measure:9s} {period:6s} {cut:13s} done", flush=True)
    return rows, profs, lags


def main():
    os.makedirs(OUT, exist_ok=True)
    F = load()
    rows, profs, lags = [], [], []

    def add(res):
        rows.extend(res[0]); profs.extend(res[1]); lags.extend(res[2])

    cuts_all = ["all", "education", "industry", "income_q", "income_q_init"]
    for period, years in PERIODS.items():
        cuts = cuts_all + (["cohort"] if period == "full" else [])
        add(run(F, "cgm", FLOOR, period, years, cuts, MAX_D.get(period, 11)))
        add(run(F, "head_earn", FLOOR, period, years, ["all", "education"], MAX_D.get(period, 11), retirees=False))
    for period in ["cgm", "full"]:                                       # robustness: no income floor
        add(run(F, "cgm", None, period, PERIODS[period], ["all", "education"], MAX_D[period]))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "psid_estimates.csv"), index=False, float_format="%.6g")
    pd.concat(profs).to_csv(os.path.join(OUT, "psid_profiles.csv"), index=False, float_format="%.6g")
    pd.concat(lags).to_csv(os.path.join(OUT, "psid_var_by_lag.csv"), index=False, float_format="%.6g")

    roll = []
    for measure in ["cgm", "head_earn"]:
        for s in ROLL_STARTS:
            r, _, _ = run(F, measure, FLOOR, f"roll{s}", (s, s + ROLL_LEN - 1), ["all", "education"], 11, retirees=False)
            roll.extend(r)
    pd.DataFrame(roll).to_csv(os.path.join(OUT, "psid_rolling.csv"), index=False, float_format="%.6g")


if __name__ == "__main__":
    main()
