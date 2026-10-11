"""PSID variance of one-year changes in residual log income by income year (annual waves, income years 1969-1996),
for the cross-source chart: head's own labor income (`head_earn`, comparable with SIPP and CPS) and CGM income.

Residuals come from the fixed-effects regression over all years by education group (psid_extend defaults).
Usage: python3 -I extend/scripts/psid_d1_by_year.py [PANEL_DIR]  -> extend/output/psid_var_d1_by_year.csv
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import incproc as ip  # noqa: E402
import psid_extend as pe  # noqa: E402


def main():
    F = pe.load()
    rows = []
    for measure in ["head_earn", "cgm"]:
        S = pe.base_sample(F, measure, pe.FLOOR)
        for e, G in S.groupby("educ3_h"):
            _, _, fhat, _ = ip.fe_regression(G, controls=pe.CONTROLS[measure])
            D = G[["unit", "income_year"]].assign(u=(G["logy"] - fhat).to_numpy(), educ=pe.EDUC[e])
            rows.append(D)
        D = pd.concat(rows[-3:])
        m = D.merge(D.assign(income_year=D["income_year"] - 1), on=["unit", "income_year", "educ"], suffixes=("", "_f"))
        m["r1"] = m["u_f"] - m["u"]
        for grp, g in [("all", m)] + list(m.groupby("educ")):
            v = g.groupby("income_year")["r1"].agg(["var", "size"]).reset_index()
            rows.append(v.assign(measure=measure, group=grp, kind="out"))
    out = pd.concat([r for r in rows if "kind" in r])
    out = out.rename(columns={"income_year": "income_year_start", "var": "var_d1", "size": "n_pairs"}).drop(columns="kind")
    out.to_csv(os.path.join(pe.OUT, "psid_var_d1_by_year.csv"), index=False, float_format="%.6g")


if __name__ == "__main__":
    main()
