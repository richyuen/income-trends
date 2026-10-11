"""Step 3: cross-source comparison and the parameter dataset, from the outputs of psid_extend.py and census_extend.py.

  source_compare.csv  PSID (head's own labor income), SIPP and CPS ASEC side by side on the same person-earnings
                      concept, by period and education: profile shape (log change of the cubic from 25 to 50 and
                      50 to 60), Var of 1- and 2-year changes, each source's shock variances, and a common
                      short-lag fit (Carroll-Samwick on lags 1-4 only, the most a SIPP panel allows).
  parameters.csv      the parameter set for the life cycle model: CGM income (default sample, income under $2,000
                      dropped), every cut and period: age-profile cubic and constant, marital and household
                      coefficients with their sample means, shock variances with bootstrap SEs, replacement rate.

Usage: python3 -I extend/scripts/compare.py
"""
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "extend", "output")
KEY = ["source", "measure", "period", "years", "cut", "group"]


def short_fit(V, max_d=4):
    """OLS of Var(r_d) on d over lags 1..max_d: (s2_perm, s2_trans)."""
    V = V[V["d"] <= max_d]
    if len(V) < 2:
        return np.nan, np.nan
    c = np.polyfit(V["d"].to_numpy(float), V["var"].to_numpy(), 1)
    return c[0], c[1] / 2


def lag_stats(L, keys):
    rows = []
    for k, V in L.groupby(keys):
        p, t = short_fit(V)
        rows.append(dict(zip(keys, k), var_d1=V.loc[V["d"] == 1, "var"].mean(), var_d2=V.loc[V["d"] == 2, "var"].mean(),
                         s2_perm_short=p, s2_trans_short=t))
    return pd.DataFrame(rows)


def main():
    pe = pd.read_csv(os.path.join(OUT, "psid_estimates.csv")).assign(source="psid")
    pl = pd.read_csv(os.path.join(OUT, "psid_var_by_lag.csv")).assign(source="psid")
    se = pd.read_csv(os.path.join(OUT, "sipp_estimates.csv"))
    sl = pd.read_csv(os.path.join(OUT, "sipp_var_by_lag.csv"))
    ce = pd.read_csv(os.path.join(OUT, "cps_estimates.csv"))
    cols = KEY + ["peak_age", "d_25_50", "d_50_60", "s2_perm", "s2_trans"]

    psid = pe[(pe["measure"] == "head_earn") & pe["period"].isin(["p1", "p2", "p3", "p4", "full"])
              & pe["cut"].isin(["all", "education"])]
    psid = psid[cols].merge(lag_stats(pl[pl["measure"] == "head_earn"], ["source", "measure", "period", "cut", "group"]),
                            on=["source", "measure", "period", "cut", "group"], how="left")
    sipp = se[se["period"].str.startswith("era") & se["cut"].isin(["all", "education"])][cols]
    sipp = sipp.merge(lag_stats(sl[sl["period"].str.startswith("era")], ["source", "period", "cut", "group"]),
                      on=["source", "period", "cut", "group"], how="left")
    cps = ce[cols + ["var_d1", "pair_years"]].copy()
    method = {"psid": "fixed effects; Carroll-Samwick lags 1-11 (22 for full)", "sipp": "synthetic-cohort profile; Carroll-Samwick lags 1-4",
              "cps": "synthetic-cohort profile; Deaton-Paxson s2_perm; s2_trans = (Var(D1) - s2_perm)/2"}
    C = pd.concat([psid, sipp, cps], ignore_index=True)
    C["method"] = C["source"].map(method)
    C.to_csv(os.path.join(OUT, "source_compare.csv"), index=False, float_format="%.5g")

    P = pe[(pe["measure"] == "cgm") & (pe["sample"] == "drop_lt2k")]
    keep = ["period", "years", "cut", "group", "n_units", "n_obs", "Tbar", "age_min", "age_max", "const", "p3_c0", "p3_c1",
            "p3_c2", "p3_c3", "married", "mean_married", "hhcomp", "mean_hhcomp", "peak_age", "growth_to_peak", "d_25_50",
            "d_50_60", "fall_peak_to_65", "level65_k1992", "s2_perm", "s2_perm_se", "s2_trans", "s2_trans_se",
            "s2_perm_yd", "s2_trans_yd", "n_lags", "repl_prof65_pens", "repl_n_ret"]
    P[keep].to_csv(os.path.join(OUT, "parameters.csv"), index=False, float_format="%.6g")
    print(C.round(4).to_string())


if __name__ == "__main__":
    main()
