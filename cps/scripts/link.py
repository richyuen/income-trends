"""Link people across adjacent CPS ASEC years (the CPS rotation puts households in months-in-sample 1-4 in March
of year t back in the sample, in months 5-8, in March of year t+1).

Usage: python3 -I cps/scripts/link.py
Input:  cps/data/asec_*.parquet (from extract.py)
Output: cps/data/asec_links.parquet  one row per matched person pair: asec_year (t), file_t, ph_seq_t, pppos_t,
                                     file_t1, ph_seq_t1, pppos_t1, plus the checks used
        cps/output/link_rates.csv    by pair of years: people 15+ in MIS 1-4 in t, matched in t+1, match rate

Method (Madrian and Lefgren 2008): candidate pairs share the household identifier (H_IDNUM; its first
15 characters, HRHHID, since 2005 adds the 5-character HRHHID2, which can change between years) and the person line number (A_LINENO), with MIS(t) in 1-4 and
MIS(t+1) = MIS(t) + 4. A pair is kept if sex agrees, race agrees, and age(t+1) - age(t) is in [-1, 3].
Households that move are replaced by the new occupants of the address, so they do not match (this is the CPS's
main source of non-match and is not random: movers are younger and more mobile).
Where linking works (output/link_rates.csv): 1988-1993 and 1996-2001 (65-76% of MIS 1-4 people), 2002-2003
(45-51%: the eligible count includes the SCHIP expansion sample), 2004-2014 (42-52%). It fails (<1%) for
1993->1994 (1994 CATI redesign), 1994->1995, 1995->1996 (1995 sample redesign) and every
pair from 2015->2016 on: from ASEC 2015 the public files' household IDs do not carry over to the
next March (IDs recur in 2016 mostly among MIS 1-4 households, i.e. they are reassigned, not followed), while
ASEC IDs still match that month's basic CPS file. Linking 2015+ would need a probabilistic match on state, MIS,
line number, sex, race, Hispanic origin, age and household composition; not attempted here.
2014 uses the 5/8 traditional file and the 3/8 redesign file together; 2017-2018 use the production (legacy)
files, so 2018 -> 2019 crosses the processing change.
"""
from pathlib import Path
import numpy as np, pandas as pd

D = Path(__file__).resolve().parent.parent
COLS = ["asec_year", "file", "ph_seq", "pppos", "h_idnum", "h_mis", "a_lineno", "sex", "race", "age"]
SKIP = {"research_updated", "bridge_updated"}


def load(year):
    fs = [f for f in sorted((D / "data").glob(f"asec_{year}_*.parquet")) if not any(s in f.name for s in SKIP)]
    if not fs: return None
    return pd.concat([pd.read_parquet(f, columns=COLS) for f in fs], ignore_index=True)


def norm_id(s):
    # first 15 characters (HRHHID); HRHHID2 is not needed for the match and bridges 2004 -> 2005
    return s.astype(str).str.strip().str[:15].str.lstrip("0")


def main():
    years = sorted({int(f.name.split("_")[1]) for f in (D / "data").glob("asec_*_*.parquet")})
    links, rates = [], []
    for t in years:
        a, b = load(t), load(t + 1)
        if a is None or b is None: continue
        a = a[a.h_mis.between(1, 4)].copy(); b = b[b.h_mis.between(5, 8)].copy()
        for x in (a, b): x["hid"] = norm_id(x.h_idnum)
        m = a.merge(b, on=["hid", "a_lineno"], suffixes=("_t", "_t1"))
        m = m[(m.h_mis_t1 == m.h_mis_t + 4)]
        ok = (m.sex_t == m.sex_t1) & (m.race_t == m.race_t1) & (m.age_t1 - m.age_t).between(-1, 3)
        good = m[ok].drop_duplicates(["file_t", "ph_seq_t", "pppos_t"], keep=False)
        good = good.drop_duplicates(["file_t1", "ph_seq_t1", "pppos_t1"], keep=False)
        rates.append(dict(asec_year=t, eligible_t=len(a), id_line_match=len(m), matched=len(good),
                          rate=round(len(good) / len(a), 3) if len(a) else np.nan))
        links.append(good[["asec_year_t", "file_t", "ph_seq_t", "pppos_t", "file_t1", "ph_seq_t1", "pppos_t1",
                           "age_t", "age_t1"]].rename(columns={"asec_year_t": "asec_year"}))
        print(rates[-1], flush=True)
    pd.concat(links, ignore_index=True).to_parquet(D / "data" / "asec_links.parquet", index=False, compression="zstd")
    (D / "output").mkdir(exist_ok=True)
    pd.DataFrame(rates).to_csv(D / "output" / "link_rates.csv", index=False)


if __name__ == "__main__":
    main()
