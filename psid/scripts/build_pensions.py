"""Pension, annuity, VA and IRA income of head and spouse from the fourth PSID extract (J366067), by family-year.

Usage: python3 -I psid/scripts/build_pensions.py RAW_DIR4 [OUT_DIR]
  RAW_DIR4 holds J366067.txt, J366067.do and cb.txt (pdftotext -layout of J366067_codebook.pdf)
  OUT_DIR  defaults to /mnt/project-files/psid (person-level output; never inside the repo)

Writes OUT_DIR/psid_pensions_family_year.parquet and the aggregate check psid/output/pensions_by_year.csv
(families, share of heads/spouses with positive amounts, mean positive amount, DK/NA count, components by year).
The parquet has one row per survey year x family (interview number `fid`),
to be merged onto psid_family_year.parquet on (year, fid). Amounts are nominal annual dollars for the income year
(survey year - 1). Variables were mapped by hand from the .do labels and checked against the codebook (PEN below);
missing-data codes and the time-unit codes of 1994-2003 come from the codebook text.

Concepts
  pens_h   head: retirement pay, pensions and annuities, incl. VA pensions (from 1984), annuities/IRAs (from 1993)
  pens_w   wife/spouse: pensions and annuities (from 1985; VA pension 1985-1992 and 2015+; IRA from 2013)
  ira_h, ira_w   IRA distributions where reported separately (2013+); already inside pens_h / pens_w
  The components are kept (pens_h_va, pens_h_ret, pens_h_ann, pens_h_oth, pens_h_ira; same for _w).
Eras
  1968-1969 head bracket only (midpoints); 1970-1983 one head item "other retirement pay, pensions, annuities";
  1984-1992 head VA + other retirement, wife VA + other retirement from 1985; 1993 head VA, retirement/pensions,
  annuities/IRAs, other retirement, wife pensions/annuities; 1994-2003 as-reported amount x time unit (annualized
  as in build.py: Month 12, Two weeks 26, Week 52, Year 1; Other/DK/NA unit -> taken as annual; full-year value over
  $250,000 from a per-period amount -> taken as annual); 2005-2023 PSID-generated annual amounts.
  Wife pensions are not available before the 1985 survey (only her "other transfer income", kept as othtr_w).
"""
import os, re, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build import Extract  # noqa: E402

BKT_MID = {0: 0, 1: 250, 2: 750, 3: 1500, 4: 2500, 5: 4000, 6: 6250, 7: 8750, 8: 10000}
IMPLAUSIBLE = 250000

# year -> {component: var}; components ending in _per are time units of the same-named amount (1994-2003)
PEN = {
    1968: dict(h_bkt="V259"), 1969: dict(h_bkt="V707"),
    1970: dict(h_ret="V1213"), 1971: dict(h_ret="V1915"), 1972: dict(h_ret="V2516"), 1973: dict(h_ret="V3069"),
    1974: dict(h_ret="V3481"), 1975: dict(h_ret="V3881"), 1976: dict(h_ret="V4396"), 1977: dict(h_ret="V5307"),
    1978: dict(h_ret="V5807"), 1979: dict(h_ret="V6418"), 1980: dict(h_ret="V7008"), 1981: dict(h_ret="V7600"),
    1982: dict(h_ret="V8293"), 1983: dict(h_ret="V8901"),
    1984: dict(h_va="V10291", h_ret="V10293"),
    1985: dict(h_va="V11436", h_ret="V11438", w_va="V11449", w_ret="V11451"),
    1986: dict(h_va="V12835", h_ret="V12837", w_va="V12856", w_ret="V12858"),
    1987: dict(h_va="V13937", h_ret="V13939", w_va="V13958", w_ret="V13960"),
    1988: dict(h_va="V14952", h_ret="V14954", w_va="V14973", w_ret="V14975"),
    1989: dict(h_va="V16452", h_ret="V16454", w_va="V16473", w_ret="V16475"),
    1990: dict(h_va="V17868", h_ret="V17870", w_va="V17889", w_ret="V17891"),
    1991: dict(h_va="V19168", h_ret="V19170", w_va="V19189", w_ret="V19191"),
    1992: dict(h_va="V20468", h_ret="V20470", w_va="V20489", w_ret="V20491"),
    1993: dict(h_va="V22043", h_ret="V22059", h_ann="V22075", h_oth="V22091", w_ret="V22317"),
}
_AS_REP = {  # 1994-2003: head VA, other (non-VA) retirement, annuities, other pension; wife pension/annuity
    1994: ("ER3310 ER3325 ER3340 ER3355", "ER3644"), 1995: ("ER6311 ER6326 ER6341 ER6356", "ER6646"),
    1996: ("ER8428 ER8443 ER8458 ER8473", "ER8763"), 1997: ("ER11322 ER11337 ER11352 ER11367", "ER11645"),
    1999: ("ER14588 ER14603 ER14618 ER14633", "ER14911"), 2001: ("ER18750 ER18766 ER18782 ER18798", "ER19095"),
    2003: ("ER22120 ER22136 ER22152 ER22168", "ER22468"),
}
for _y, (_h, _w) in _AS_REP.items():
    d = {}
    for comp, v in zip(["h_va", "h_ret", "h_ann", "h_oth"], _h.split()):
        d[comp] = v; d[comp + "_per"] = "ER%d" % (int(v[2:]) + 1)
    d["w_ret"] = _w; d["w_ret_per"] = "ER%d" % (int(_w[2:]) + 1)
    PEN[_y] = d
_GEN = {  # 2005-2023 generated annual amounts: head VA, retirement/pensions, annuities, IRAs, other retirement
    2005: ("ER27960 ER27962 ER27964 - ER27966", "- ER27988 - - -"),
    2007: ("ER40950 ER40952 ER40954 - ER40956", "- ER40978 - - -"),
    2009: ("ER46858 ER46860 ER46862 - ER46864", "- ER46886 - - -"),
    2011: ("ER52266 ER52268 ER52270 - ER52272", "- ER52294 - - -"),
    2013: ("ER58067 ER58069 ER58071 ER58073 ER58075", "- ER58097 ER58099 ER58101 ER58103"),
    2015: ("ER65260 ER65262 ER65264 ER65266 ER65268", "ER65290 ER65292 ER65294 ER65296 ER65298"),
    2017: ("ER71337 ER71339 ER71341 ER71343 ER71345", "ER71367 ER71369 ER71371 ER71373 ER71375"),
    2019: ("ER77359 ER77361 ER77363 ER77365 ER77367", "ER77389 ER77391 ER77393 ER77395 ER77397"),
    2021: ("ER81686 ER81688 ER81690 ER81692 ER81694", "ER81716 ER81718 ER81720 ER81722 ER81724"),
    2023: ("ER85540 ER85542 ER85544 ER85546 ER85548", "ER85570 ER85572 ER85574 ER85576 ER85578"),
}
for _y, (_h, _w) in _GEN.items():
    d = {}
    for p, s in (("h", _h), ("w", _w)):
        for comp, v in zip(["va", "ret", "ann", "ira", "oth"], s.split()):
            if v != "-": d[f"{p}_{comp}"] = v
    PEN[_y] = d
# Wife's other transfer income (excludes ADC/AFDC, welfare, SS, SSI; includes her pensions), 1976-1983
OTHTR_W = {1976: "V4402", 1977: "V5314", 1978: "V5813", 1980: "V7014", 1981: "V7606", 1982: "V8299", 1983: "V8907"}
PER_TEXT = {"week": 52, "two weeks": 26, "month": 12, "three months": 4, "six months": 2, "year": 1}


def codebook(path):
    """var -> list of (code, text) value lines from the codebook text."""
    out, cur = {}, None
    for line in open(path, encoding="latin-1"):
        m = re.match(r"^((?:V|ER)\d+)\s+\"", line)
        if m:
            cur = m.group(1); out[cur] = []; continue
        m = re.match(r"^\s+([\d,]+(?:\.\d+)?)\s+(\S.*)$", line)
        if cur and m:
            out[cur].append((float(m.group(1).replace(",", "")), m.group(2).strip()))
    return out


def na_codes(vals):
    return [c for c, t in vals if t.startswith("DK") or t.startswith("NA")]


def per_map(vals):
    m = {}
    for c, t in vals:
        k = t.lower().split(";")[0].strip()
        if k in PER_TEXT: m[int(c)] = PER_TEXT[k]
    return m


def main():
    raw = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "/mnt/project-files/psid"
    X = Extract(os.path.join(raw, "J366067.txt"), os.path.join(raw, "J366067.do"))
    cb = codebook(os.path.join(raw, "cb.txt"))
    labels = dict(re.findall(r"label variable\s+(\w+)\s+\"([^\"]*)\"", open(os.path.join(raw, "J366067.do")).read()))
    intv_var = {1968: "ER30001"}
    for v, lab in labels.items():
        m = re.match(r"^(\d{4}) INTERVIEW NUMBER", lab)
        if m: intv_var[int(m.group(1))] = v
    rows, log = [], []
    for y, comps in sorted(PEN.items()):
        intv = X.get(intv_var[y]).copy()
        if y == 1968:  # ER30001 is everyone's 1968 family ID; keep only people who were in a 1968 FU
            intv[X.get("ER30003") <= 0] = 0
        # family-file values are the same for every member of the FU: take the first member of each family
        first = pd.DataFrame({"fid": intv}).query("fid > 0").drop_duplicates("fid").index.to_numpy()
        f = pd.DataFrame({"year": y, "fid": intv[first].astype(np.int64)})
        val = {}
        for comp, v in comps.items():
            if comp.endswith("_per"): continue
            x = X.get(v)[first].copy()
            na = np.isin(x, na_codes(cb.get(v, [])))
            x[na] = np.nan
            if comp == "h_bkt":
                x = pd.Series(x).map(BKT_MID).to_numpy(dtype=float)  # 9 = NA -> NaN
                comp = "h_ret"
            if comp + "_per" in comps:
                pv = comps[comp + "_per"]
                pm = per_map(cb.get(pv, []))
                assert pm, f"no time-unit codes parsed for {pv}"
                code = X.get(pv)[first]
                ppy = pd.Series(code).map(pm).to_numpy(dtype=float)
                assumed = (x > 0) & np.isnan(ppy)
                implaus = (x > 0) & (ppy > 1) & (x * ppy > IMPLAUSIBLE)
                p = np.where(assumed | implaus | (x == 0) | np.isnan(x), 1.0, ppy)
                log.append(f"{y} {comp} {v}: {int((x > 0).sum())} positive, unit assumed annual {int(assumed.sum())}, "
                           f"implausible taken as annual {int(implaus.sum())}, amount DK/NA {int(na.sum())}")
                x = x * p
            val[comp] = x
        z = np.zeros(len(f))
        for p in ("h", "w"):
            parts = [k for k in ("va", "ret", "ann", "ira", "oth") if f"{p}_{k}" in val]
            for k in ("va", "ret", "ann", "ira", "oth"):
                f[f"pens_{p}_{k}"] = val.get(f"{p}_{k}", np.nan)
            if parts:
                tot = z.copy()
                for k in parts: tot = tot + val[f"{p}_{k}"]   # NaN if any part is DK/NA
                f[f"pens_{p}"] = tot
            else:
                f[f"pens_{p}"] = np.nan
            f[f"pens_{p}_parts"] = "+".join(parts)
            f[f"ira_{p}"] = val.get(f"{p}_ira", np.nan)
        f["othtr_w"] = (np.where(np.isin(X.get(OTHTR_W[y])[first], na_codes(cb.get(OTHTR_W[y], []))), np.nan,
                                 X.get(OTHTR_W[y])[first]) if y in OTHTR_W else np.nan)
        rows.append(f)
    P = pd.concat(rows, ignore_index=True)
    P.to_parquet(os.path.join(out, "psid_pensions_family_year.parquet"), index=False)
    print("\n".join(log))
    s = P.groupby("year").agg(n=("fid", "size"), h_pos=("pens_h", lambda x: (x > 0).mean()),
                              h_mean_pos=("pens_h", lambda x: x[x > 0].mean()), h_na=("pens_h", lambda x: x.isna().sum()),
                              w_pos=("pens_w", lambda x: (x > 0).mean()), w_mean_pos=("pens_w", lambda x: x[x > 0].mean()),
                              parts_h=("pens_h_parts", "first"), parts_w=("pens_w_parts", "first"))
    print(s.round(3).to_string())
    s.round(4).to_csv(os.path.join(os.path.dirname(HERE), "output", "pensions_by_year.csv"))
    return P


if __name__ == "__main__":
    main()
