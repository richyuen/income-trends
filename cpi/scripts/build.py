"""Annual price indexes for deflating nominal earnings.

Usage: python3 -I cpi/scripts/build.py [RAW_DIR]   (default /tmp/it_cpi; downloads are small)
Output: cpi/data/price_indexes_annual.csv, one row per calendar year, columns:
  cpi_u        CPI-U, U.S. city average, all items, NSA, annual mean of months (FRED CPIAUCNS; BLS CUUR0000SA0)
  c_cpi_u      Chained CPI-U, NSA, annual mean (FRED SUUR0000SA0, Dec 1999 = 100), 2000 on
  pce          PCE chain-type price index, annual mean of months (FRED PCEPI, 2017 = 100)
  census       the deflator Census uses for its historical income tables, backed out of Tables P-36 and P-38
               (current-dollar / 2025-dollar medians, 8 cells a year, median ratio), 2025 = 1.
               Census: C-CPI-U from 2000, R-CPI-U-RS before 2000 (www.census.gov historical income table notes).
               The tables round medians to $10, so this index carries rounding error of up to ~0.1% in early years.
  Note: BLS published no October 2025 CPI (data not collected during the shutdown); FRED's 2025 annual means
  here average the 11 published months.
  *_2025       each index rescaled to 2025 = 1 (multiply nominal dollars by 1 / index_2025 to get 2025 dollars)
BLS's own site (www.bls.gov, download.bls.gov) refuses this environment, so the BLS series come through FRED.
"""
import io, subprocess, sys
from pathlib import Path
import numpy as np, pandas as pd

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/it_cpi"); RAW.mkdir(parents=True, exist_ok=True)
OUT = Path(__file__).resolve().parent.parent / "data" / "price_indexes_annual.csv"
FRED = {"cpi_u": "CPIAUCNS", "c_cpi_u": "SUUR0000SA0", "pce": "PCEPI"}
HIST = "https://www2.census.gov/programs-surveys/cps/tables/time-series/historical-income-people"


def fetch(url, name):
    p = RAW / name
    if not p.exists():
        subprocess.run(["curl", "-sS", "-fL", "--retry", "5", "-o", str(p), url], check=True)
    return p


def fred(code):
    d = pd.read_csv(fetch(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}", f"{code}.csv"))
    d.columns = ["date", "v"]; d["v"] = pd.to_numeric(d.v, errors="coerce")
    d["year"] = d.date.str[:4].astype(int)
    g = d.groupby("year").v.agg(["mean", "count"])
    # complete years, plus 2025: October 2025 was never collected (federal shutdown), so 2025 = mean of 11 months
    return g.loc[(g["count"] == 12) | ((g.index == 2025) & (g["count"] == 11)), "mean"]


def census_index():
    """ratio current$ / 2025$ for each median cell in P-36 and P-38 (all races), by income year"""
    rows = []
    for t in ["p36ar", "p38ar"]:
        d = pd.read_excel(fetch(f"{HIST}/{t}.xlsx", f"{t}.xlsx"), header=None)
        for _, r in d.iloc[9:].iterrows():
            y = str(r[0]).split(" ")[0]
            if not y.isdigit(): continue
            for cur, con in [(2, 3), (5, 6)]:
                try: rows.append((int(y), float(r[cur]) / float(r[con])))
                except (TypeError, ValueError): pass
    c = pd.DataFrame(rows, columns=["year", "ratio"])
    return c.groupby("year").ratio.median()       # duplicate years (2013, 2017 two files) agree to rounding


def main():
    s = {k: fred(v) for k, v in FRED.items()}
    s["census"] = census_index()
    d = pd.DataFrame(s); d.index.name = "year"
    d = d[d.index >= 1947]
    for k in list(s):
        d[f"{k}_2025"] = d[k] / d.loc[2025, k]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.round(6).to_csv(OUT)
    print(d.loc[[1960, 1987, 1999, 2000, 2010, 2024, 2025]].round(4).to_string())
    # check: Census index should track R-CPI-U-RS pre-2000 and C-CPI-U from 2000
    x = d.loc[2000:2025]
    print("max |census_2025 - c_cpi_u_2025| 2000-2025:", float((x.census_2025 - x.c_cpi_u_2025).abs().max()).__round__(4))


if __name__ == "__main__":
    main()
