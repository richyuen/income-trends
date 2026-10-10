"""Check the CPS ASEC extract against Census's published Table P-38 (full-time, year-round workers 15+ with
earnings: number and median earnings by sex, current dollars), income years 1987-2025.

Usage: python3 -I cps/scripts/validate.py [RAW_DIR]   (P-38 is downloaded to RAW_DIR, default /tmp/it_cpi)
Output: cps/output/validate_p38.csv and a printed summary.

Definitions (Census): full-time, year-round = worked 50+ weeks last year (WKSWORK) and usually 35+ hours a week
(HRSWK); "with earnings" = PEARNVAL != 0; weight MARSUPWT. Census computes medians by linear interpolation within
$2,500 brackets; med_interp reproduces that, med_raw is the plain weighted median.
P-38 lists 2013 and 2017 twice (the 2014 split-sample files; the 2018 legacy file and its updated-processing
re-run), so each extract file is matched to the closest P-38 row for its year and the row label is reported.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/it_cpi")
D = Path(__file__).resolve().parent.parent
HIST = "https://www2.census.gov/programs-surveys/cps/tables/time-series/historical-income-people"


def wmedian(x, w):
    o = np.argsort(x); x, w = x[o], w[o]; c = np.cumsum(w)
    return float(x[np.searchsorted(c, c[-1] / 2)])


def interp_median(x, w, width=2500):
    """Census-style: find the $2,500 bracket holding the median, interpolate linearly inside it"""
    half = w.sum() / 2
    lo = np.floor(x / width) * width
    g = pd.Series(w).groupby(lo).sum().sort_index()
    cum = g.cumsum()
    b = cum.index[np.searchsorted(cum.values, half)]
    below = cum.loc[b] - g.loc[b]
    return float(b + width * (half - below) / g.loc[b])


def p38():
    import subprocess
    p = RAW / "p38ar.xlsx"
    if not p.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sS", "-fL", "-o", str(p), f"{HIST}/p38ar.xlsx"], check=True)
    d = pd.read_excel(p, header=None).iloc[9:, :6]
    d.columns = ["label", "n_m", "med_m", "_", "n_f", "med_f"]
    d = d[d.label.astype(str).str[:4].str.isdigit()].drop(columns="_")
    d["year"] = d.label.astype(str).str[:4].astype(int)
    return d


def main():
    pub = p38()
    rows = []
    for f in sorted((D / "data").glob("asec_*.parquet")):
        a = pd.read_parquet(f, columns=["income_year", "file", "sex", "wkswork", "hrswk", "pearnval", "marsupwt"])
        yr, lab = int(a.income_year.iloc[0]), a.file.iloc[0]
        ft = a[(a.wkswork >= 50) & (a.hrswk >= 35) & (a.pearnval != 0)]
        r = {"income_year": yr, "file": lab}
        for s, k in [(1, "m"), (2, "f")]:
            x = ft[ft.sex == s]
            r[f"n_{k}"] = x.marsupwt.sum() / 1e3
            r[f"med_raw_{k}"] = wmedian(x.pearnval.values.astype(float), x.marsupwt.values)
            r[f"med_interp_{k}"] = interp_median(x.pearnval.values.astype(float), x.marsupwt.values)
        cand = pub[pub.year == yr]
        if len(cand):
            j = (cand.med_m.astype(float) - r["med_interp_m"]).abs().add((cand.med_f.astype(float) - r["med_interp_f"]).abs()).idxmin()
            c = cand.loc[j]
            r.update(p38_label=c.label, p38_n_m=c.n_m, p38_med_m=c.med_m, p38_n_f=c.n_f, p38_med_f=c.med_f)
        rows.append(r)
    v = pd.DataFrame(rows)
    for k in "mf":
        v[f"dn_{k}_pct"] = 100 * (v[f"n_{k}"] / v[f"p38_n_{k}"].astype(float) - 1)
        v[f"dmed_{k}_pct"] = 100 * (v[f"med_interp_{k}"] / v[f"p38_med_{k}"].astype(float) - 1)
    (D / "output").mkdir(exist_ok=True)
    v.round(2).to_csv(D / "output" / "validate_p38.csv", index=False)
    pd.set_option("display.width", 200)
    print(v[["income_year", "file", "p38_label", "n_m", "p38_n_m", "med_interp_m", "p38_med_m", "med_interp_f",
             "p38_med_f", "dn_m_pct", "dn_f_pct", "dmed_m_pct", "dmed_f_pct"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
