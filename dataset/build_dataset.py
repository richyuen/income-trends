"""Step 4: the parameter dataset for the life cycle model, built from extend/output/parameters.csv (PSID, CGM income,
default sample: real income under $2,000 in 1992 dollars dropped).

Writes
  dataset/income_process_parameters.csv  long format: one row per period x cut x group x parameter (value, SE, unit)
  dataset/age_profiles.csv               deterministic income by age 20-65 for every period x cut x group:
                                         log level and level in thousands of 1992 and 2024 dollars (CPI-U)
  dataset/income_process_model.json      the recommended sets (baseline 1969-2022 and "today" 2007-2022 by
                                         education) in the shape a model reads: profile, shocks, replacement rate

Model (CGM 2005, Eq. 1-3): log Y_it = const + married*m + hhcomp*h + f(age) + v_it + e_it, v_it = v_i,t-1 + u_it,
f(age) = c0 + c1*age + c2*age^2/10 + c3*age^3/100; Var(u) = s2_perm, Var(e) = s2_trans; retirement income =
lambda * exp(const + married*mean_married + hhcomp*mean_hhcomp + f(65)).

Usage: python3 -I dataset/build_dataset.py
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dataset")
DEFAULT_REPL = {"no_high_school": 0.87, "high_school": 0.78, "college": 0.68}   # Richard, 2026-10-11

PARAMS = [  # column, parameter name, unit, description
    ("const", "const", "log 1992 $000", "Fixed-effects constant (Stata xtreg, fe convention)"),
    ("p3_c0", "profile_c0", "log points", "Age profile cubic: intercept"),
    ("p3_c1", "profile_c1", "log points per year", "Age profile cubic: coefficient on age"),
    ("p3_c2", "profile_c2", "log points", "Age profile cubic: coefficient on age^2/10"),
    ("p3_c3", "profile_c3", "log points", "Age profile cubic: coefficient on age^3/100"),
    ("married", "married", "log points", "Effect of a spouse present"),
    ("mean_married", "mean_married", "share", "Sample share with a spouse present"),
    ("hhcomp", "hhcomp", "log points per person", "Effect of each family member besides head and spouse"),
    ("mean_hhcomp", "mean_hhcomp", "persons", "Sample mean of family members besides head and spouse"),
    ("age_min", "age_min", "years", "Youngest age in the estimation"),
    ("age_max", "age_max", "years", "Oldest age in the estimation"),
    ("peak_age", "peak_age", "years", "Age at which the cubic peaks"),
    ("d_25_50", "growth_25_50", "log points", "Change of the profile from age 25 to 50"),
    ("d_50_60", "change_50_60", "log points", "Change of the profile from age 50 to 60"),
    ("level65_k1992", "level_65", "1992 $000", "Fitted income at 65, controls at sample means"),
    ("s2_perm", "s2_perm", "log points squared", "Variance of permanent shocks (Carroll-Samwick)"),
    ("s2_trans", "s2_trans", "log points squared", "Variance of transitory shocks (Carroll-Samwick)"),
    ("repl_prof65_pens", "replacement_rate", "ratio", "Retired income incl. pensions (65-75) / fitted level at 65"),
    ("n_units", "n_units", "count", "Person x education units"),
    ("n_obs", "n_obs", "count", "Person-years"),
]
SE = {"s2_perm": "s2_perm_se", "s2_trans": "s2_trans_se", "married": None}


def cubic(c, age):
    a = np.asarray(age, float)
    return c[0] + c[1] * a + c[2] * a ** 2 / 10 + c[3] * a ** 3 / 100


def main():
    P = pd.read_csv(os.path.join(ROOT, "extend", "output", "parameters.csv"))
    cpi = pd.read_csv(os.path.join(ROOT, "cpi", "data", "price_indexes_annual.csv")).set_index("year")["cpi_u"]
    to2024 = cpi.loc[2024] / cpi.loc[1992]

    rows = []
    for _, r in P.iterrows():
        for col, name, unit, desc in PARAMS:
            if pd.isna(r.get(col)):
                continue
            se_col = SE.get(col)
            rows.append(dict(source="psid", income="cgm_household", sample="drop_lt2k_1992usd", period=r["period"],
                             years=r["years"], cut=r["cut"], group=r["group"], parameter=name, value=r[col],
                             se=r[se_col] if se_col else np.nan, unit=unit, description=desc))
    L = pd.DataFrame(rows)
    L.to_csv(os.path.join(OUT, "income_process_parameters.csv"), index=False, float_format="%.6g")

    prof = []
    for _, r in P.iterrows():
        c = [r["p3_c0"], r["p3_c1"], r["p3_c2"], r["p3_c3"]]
        ctrl = r["married"] * r["mean_married"] + r["hhcomp"] * r["mean_hhcomp"]
        for a in range(int(r["age_min"]), int(r["age_max"]) + 1):
            lg = r["const"] + ctrl + cubic(c, a)
            prof.append(dict(period=r["period"], years=r["years"], cut=r["cut"], group=r["group"], age=a,
                             log_level=lg, level_k1992=np.exp(lg), level_k2024=np.exp(lg) * to2024))
    pd.DataFrame(prof).to_csv(os.path.join(OUT, "age_profiles.csv"), index=False, float_format="%.6g")

    def block(period):
        out = {}
        for g in ["no_high_school", "high_school", "college"]:
            r = P[(P["period"] == period) & (P["cut"] == "education") & (P["group"] == g)].iloc[0]
            out[g] = dict(
                age_range=[int(r["age_min"]), int(r["age_max"])],
                const=r["const"], married=r["married"], mean_married=r["mean_married"], hhcomp=r["hhcomp"],
                mean_hhcomp=r["mean_hhcomp"],
                profile_cubic=dict(c0=r["p3_c0"], c1=r["p3_c1"], c2=r["p3_c2"], c3=r["p3_c3"],
                                   form="c0 + c1*age + c2*age^2/10 + c3*age^3/100"),
                s2_perm=r["s2_perm"], s2_perm_se=r["s2_perm_se"], s2_trans=r["s2_trans"], s2_trans_se=r["s2_trans_se"],
                replacement_rate_estimated=r["repl_prof65_pens"], level_65_k1992=r["level65_k1992"])
        return out

    model = {
        "description": "CGM (2005) labor income process re-estimated from PSID; household labor income plus transfers, "
                       "thousands of 1992 dollars (CPI-U); SRC male heads 20-65 (22-65 college); incomes under $2,000 "
                       "(1992 $) dropped. Variances are in log points squared.",
        "equation": "log Y = const + married*m + hhcomp*h + f(age) + v + e; v_t = v_{t-1} + u; Var(u)=s2_perm; Var(e)=s2_trans; "
                    "retirement income = replacement_rate * exp(const + married*mean_married + hhcomp*mean_hhcomp + f(65))",
        "cpi_u_1992_to_2024": to2024,
        "replacement_rate_default": DEFAULT_REPL,
        "replacement_rate_default_note": "Richard's choice (2026-10-11): retired income incl. pensions over the profile at 65, "
                                         "CGM window 1969-1991, full sample (cgm/README.md).",
        "baseline_1969_2022": block("full"),
        "recent_2007_2022": block("p4"),
        "cgm_window_1969_1991": block("cgm"),
    }
    with open(os.path.join(OUT, "income_process_model.json"), "w") as f:
        json.dump(model, f, indent=2, default=float)
    print(f"{len(L)} parameter rows, {len(prof)} profile rows")


if __name__ == "__main__":
    main()
