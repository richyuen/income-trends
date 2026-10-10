"""Extract a working-age labor earnings file from every CPS ASEC (March supplement) public-use file, 1988-2026.

Usage: python3 -I cps/scripts/extract.py RAW_DIR [YEAR ...]
  RAW_DIR holds (or receives) the raw downloads and NBER dictionaries; keep it outside the repo (e.g. /tmp/it_cps/raw).
  YEARs (ASEC years) limit the run; default is all.
Output: cps/data/asec_<ASECYEAR>_<file>.parquet, one row per person aged 15+ (Census's earnings universe), nominal $.
  Income and work-experience items refer to the calendar year before the survey (income_year = asec_year - 1).

Sources (same files and URLs as richyuen/retirement-trends cps/ and spending/cps_income/, extended back to 1988):
  ASEC 1988-1997  NBER re-hosts of the Census public-use files: https://data.nber.org/cps/cpsmarYY.zip
                  (Census's own datasets tree starts at March 1998).
  ASEC 1998-2018  Census fixed-width files, www2.census.gov/programs-surveys/cps/datasets/YYYY/march/
                  (2014: 5/8 traditional-questionnaire file and 3/8 redesigned-questionnaire file).
  ASEC 2017, 2018 research / bridge files re-processed with the updated (2019+) system, CSV.
  ASEC 2019-2026  Census CSV files asecpubYYcsv.zip (hhpub, pppub).
Fixed-width positions come from NBER's Stata dictionaries (data.nber.org/data/progs/cps/cpsmarYY.dct, one per
year, hierarchical: household record type 1, family 2, person 3). They agree with the positions the
retirement-trends scripts took from Census's own dictionaries (cpsmarYY.pdf), and every year is checked here:
PEARNVAL = WSAL_VAL + SEMP_VAL + FRSE_VAL, ages 0-90, sex 1-2, weighted population.
"""
import gzip, io, re, sys, zipfile, subprocess
from multiprocessing import Pool
from pathlib import Path
import numpy as np, pandas as pd

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/it_cps/raw")
ONLY = {int(a) for a in sys.argv[2:]}
OUT = Path(__file__).resolve().parent.parent / "data"
B = "https://www2.census.gov/programs-surveys/cps/datasets"
X = "https://www2.census.gov/programs-surveys/demo/datasets/income-poverty/time-series/data-extracts"
NBER = "https://data.nber.org"

# (asec_year, file label) -> (data URL, NBER dictionary name)
LEGACY = {(1900 + y, "production"): (f"{NBER}/cps/cpsmar{y}.zip", f"cpsmar{y}") for y in range(88, 98)}
LEGACY.update({
    (1998, "production"): (f"{B}/1998/march/mar98supp.cps.gz", "cpsmar98"),
    (1999, "production"): (f"{B}/1999/march/mar99supp.cps.gz", "cpsmar99"),
    (2000, "production"): (f"{B}/2000/march/mar00supp.cps.gz", "cpsmar00"),
    (2001, "production"): (f"{B}/2001/march/mar01supp.dat.gz", "cpsmar01"),
    (2002, "production"): (f"{B}/2002/march/mar02supp.dat.gz", "cpsmar02"),
    (2003, "production"): (f"{B}/2003/march/asec2003.pub.gz", "cpsmar03"),
    (2004, "production"): (f"{B}/2004/march/asec2004.pub.gz", "cpsmar04"),
    (2005, "production"): (f"{B}/2005/march/asec2005_pubuse.pub.gz", "cpsmar05"),
    (2006, "production"): (f"{B}/2006/march/asec2006_pubuse.pub.gz", "cpsmar06"),
    (2007, "production"): (f"{B}/2007/march/asec2007_pubuse_tax2.dat.gz", "cpsmar07"),
    (2008, "production"): (f"{B}/2008/march/asec2008_pubuse.dat.gz", "cpsmar08"),
    (2009, "production"): (f"{B}/2009/march/asec2009_pubuse.dat.gz", "cpsmar09"),
    (2010, "production"): (f"{B}/2010/march/asec2010_pubuse.dat.gz", "cpsmar10"),
    (2011, "production"): (f"{B}/2011/march/asec2011_pubuse.dat.gz", "cpsmar11"),
    (2012, "production"): (f"{B}/2012/march/asec2012_pubuse.dat.gz", "cpsmar12"),
    (2013, "production"): (f"{B}/2013/march/asec2013_pubuse.dat.gz", "cpsmar2013"),
    (2014, "traditional_5x8"): (f"{B}/2014/march/asec2014_pubuse_tax_fix_5x8_2017.dat.gz", "cpsmar2014t"),
    (2014, "redesign_3x8"): (f"{B}/2014/march/asec2014_pubuse_3x8_rerun_v2.dat.gz", "cpsmar2014r"),
    (2015, "production"): (f"{B}/2015/march/asec2015_pubuse.dat.gz", "cpsmar2015"),
    (2016, "production"): (f"{B}/2016/march/asec2016_pubuse_v3.dat.gz", "cpsmar2016"),
    (2017, "production"): (f"{B}/2017/march/asec2017_pubuse.dat.gz", "cpsmar2017"),
    (2018, "production"): (f"{B}/2018/march/asec2018_pubuse.dat.gz", "cpsmar2018"),
})
NEW = {
    (2017, "research_updated"): (f"{X}/2017/cps-asec-research-file/pppub17.csv", f"{X}/2017/cps-asec-research-file/hhpub17.csv"),
    (2018, "bridge_updated"): (f"{X}/2018/cps-asec-bridge-file/pppub18.csv", f"{X}/2018/cps-asec-bridge-file/hhpub18.csv"),
    **{(2000 + y, "production"): (f"{B}/{2000+y}/march/asecpub{y}csv.zip", None) for y in range(19, 27)},
}

# canonical name -> candidate source names (first found wins; the source used is recorded per file)
PERSON = {
    "ph_seq": ["ph_seq"], "pppos": ["pppos"], "a_lineno": ["a_lineno", "pulineno"], "peridnum": ["peridnum"],
    "pf_seq": ["pf_seq"], "a_famnum": ["a_famnum", "prfamnum"], "a_famrel": ["a_famrel", "prfamrel"], "a_exprrp": ["a_exprrp"],
    "age": ["a_age", "peage"], "sex": ["a_sex", "pesex"], "a_maritl": ["a_maritl", "prmarsta"],
    "a_hga": ["a_hga", "peeduca"], "a_hgc": ["a_hgc"],                       # 1988-91: grade attended/completed; 1992+: degree
    "race": ["prdtrace", "a_race", "perace"], "hisp": ["pehspnon", "a_reorgn", "prorigin"],
    # labor force now (March) and work last year
    "pemlr": ["pemlr"], "a_wkstat": ["a_wkstat"], "a_clswkr": ["a_clswkr"], "a_mjind": ["a_mjind", "prmjind1"],
    "a_mjocc": ["a_mjocc", "mjocc", "prmjocc1"],
    "workyn": ["workyn"], "wrk_ck": ["wrk_ck"], "wkswork": ["wkswork"], "hrswk": ["hrswk"], "wewkrs": ["wewkrs"],
    "lkweeks": ["lkweeks"],
    # longest job last year
    "ljcw": ["ljcw"], "industry": ["industry"], "occup": ["occup"], "weind": ["weind"], "wemind": ["wemind"],
    "poccu2": ["poccu2"], "wemocg": ["wemocg"],
    # earnings last year
    "ern_val": ["ern_val"], "ern_srce": ["ern_srce"], "ern_otr": ["ern_otr"], "wsal_val": ["wsal_val"],
    "semp_val": ["semp_val"], "frse_val": ["frse_val"], "pearnval": ["pearnval"], "ptotval": ["ptotval"],
    "i_ernval": ["i_ernval"], "i_wsval": ["i_wsval"], "i_seval": ["i_seval"], "i_frmval": ["i_frmval"],
    "tcernval": ["tcernval"], "tcwsval": ["tcwsval"], "tcseval": ["tcseval"], "tcffmval": ["tcffmval"],
    # weights (2 implied decimals in the fixed-width files)
    "marsupwt": ["marsupwt"], "a_fnlwgt": ["a_fnlwgt"], "a_ernlwt": ["a_ernlwt"],
}
HOUSE = {"h_seq": ["h_seq"], "h_idnum": ["h_idnum"], "h_idnum1": ["h_idnum1"], "h_idnum2": ["h_idnum2"],
         "h_mis": ["h_mis"], "h_numper": ["h_numper", "hrnumhou"], "h_hhtype": ["h_hhtype", "hrintsta"],
         "gestfips": ["gestfips"], "hg_st60": ["hg_st60", "gestcen"]}
STR = {"peridnum", "h_idnum", "h_idnum1", "h_idnum2"}
WEIGHTS = ["marsupwt", "a_fnlwgt", "a_ernlwt"]


def fetch(url, name=None):
    p = RAW / (name or url.rsplit("/", 1)[1])
    if not p.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sS", "-fL", "--retry", "5", "-o", str(p) + ".part", url], check=True)
        Path(str(p) + ".part").rename(p)
    return p


def parse_dct(path):
    """NBER .dct -> {record letter: {name: (start, width)}}"""
    recs, cur = {}, None
    for line in open(path, encoding="latin-1"):
        m = re.match(r"\s*_column\(\s*(\d+)\s*\)\s+\S+\s+(\S+)\s+%(\d+)", line)
        if not m: continue
        start, name, w = int(m[1]), m[2].lower(), int(m[3])
        if start == 1 and name.endswith("record"): cur = name[0]; recs[cur] = {}
        if cur: recs[cur].setdefault(name, (start, w))
    return recs


def pick(avail, spec):
    use = {}
    for canon, cands in spec.items():
        for c in cands:
            if c in avail: use[canon] = c; break
    return use


def open_text(path):
    if path.suffix == ".zip":   # NBER zips carry extra fields Python's zipfile rejects; stream with unzip
        pr = subprocess.Popen(["unzip", "-p", str(path)], stdout=subprocess.PIPE)
        return io.TextIOWrapper(pr.stdout, encoding="latin-1")
    return gzip.open(path, "rt", encoding="latin-1")


def read_legacy(path, dct):
    lay = parse_dct(dct)
    pu, hu = pick(lay["p"], PERSON), pick(lay["h"], HOUSE)
    psl = {k: (lay["p"][v][0] - 1, lay["p"][v][0] - 1 + lay["p"][v][1]) for k, v in pu.items()}
    hsl = {k: (lay["h"][v][0] - 1, lay["h"][v][0] - 1 + lay["h"][v][1]) for k, v in hu.items()}
    rows, hh = [], None
    with open_text(path) as f:
        for line in f:
            t = line[0]
            if t == "1":
                hh = [line[a:b] for a, b in hsl.values()]
            elif t == "3":
                rows.append([line[a:b] for a, b in psl.values()] + hh)
    d = pd.DataFrame(rows, columns=list(psl) + list(hsl))
    for c in d.columns:
        d[c] = d[c].str.strip()
        if c not in STR: d[c] = pd.to_numeric(d[c], errors="coerce")
    for w in WEIGHTS:
        if w in d: d[w] = d[w] / 100
    src = {**pu, **hu}
    return d, src


def read_new(yr, lab, purl, hurl):
    if purl.endswith(".zip"):
        z = zipfile.ZipFile(fetch(purl))
        pfh = z.open(next(n for n in z.namelist() if re.search(r"pppub\d+\.csv$", n)))
        hfh = z.open(next(n for n in z.namelist() if re.search(r"hhpub\d+\.csv$", n)))
    else:
        tag = "research2017_" if yr == 2017 else "bridge2018_"
        pfh = open(fetch(purl, tag + purl.rsplit("/", 1)[1]), "rb"); hfh = open(fetch(hurl, tag + hurl.rsplit("/", 1)[1]), "rb")
    pcols = pd.read_csv(pfh, nrows=0).columns; pfh.seek(0)
    hcols = pd.read_csv(hfh, nrows=0).columns; hfh.seek(0)
    pu, hu = pick({c.lower(): c for c in pcols}, PERSON), pick({c.lower(): c for c in hcols}, HOUSE)
    pmap = {pcols[[c.lower() for c in pcols].index(v)]: k for k, v in pu.items()}
    hmap = {hcols[[c.lower() for c in hcols].index(v)]: k for k, v in hu.items()}
    p = pd.read_csv(pfh, usecols=list(pmap), dtype={c: str for c in pmap if pmap[c] in STR}).rename(columns=pmap)
    h = pd.read_csv(hfh, usecols=list(hmap), dtype={c: str for c in hmap if hmap[c] in STR}).rename(columns=hmap)
    d = p.merge(h, left_on="ph_seq", right_on="h_seq", how="left", validate="m:1")
    for w in WEIGHTS:
        if w in d and d[w].max() > 1e6: d[w] = d[w] / 100   # some CSVs keep 2 implied decimals
    return d, {**pu, **hu}


def finish(d, src, yr, lab, system):
    assert d.h_seq.notna().all() and (d.ph_seq == d.h_seq).all(), "person not matched to household"
    assert d.age.between(0, 99).all() and d.sex.isin([1, 2]).all(), (d.age.describe(), d.sex.unique())
    gap = d.pearnval - d.wsal_val - d.semp_val - d.frse_val
    pop = d.marsupwt.sum() / 1e6
    d = d[d.age >= 15].copy()
    if "h_idnum1" in d and "h_idnum" not in d:
        d["h_idnum"] = d.h_idnum1.astype(str) + d.h_idnum2.astype(str)
        d = d.drop(columns=["h_idnum1", "h_idnum2"])
    d["asec_year"], d["income_year"], d["file"], d["system"] = yr, yr - 1, lab, system
    d["race_src"], d["hisp_src"] = src.get("race"), src.get("hisp")
    for c in d.columns:
        if d[c].dtype == "float64" and c not in WEIGHTS and d[c].notna().all() and (d[c] % 1 == 0).all():
            d[c] = d[c].astype("int64")
    msg = (f"{yr} {lab:17s} persons15+ {len(d):6d} pop(M) {pop:6.1f} earn!=parts {int((gap != 0).sum())} "
           f"earners {int((d.pearnval != 0).sum())} missing {sorted(set(PERSON) - set(src))}")
    return d, msg


def run(task):
    (yr, lab), kind = task
    if kind == "legacy":
        url, dname = LEGACY[(yr, lab)]
        dct = fetch(f"{NBER}/data/progs/cps/{dname}.dct", "nber_" + dname + ".dct")
        d, src = read_legacy(fetch(url), dct)
        d, msg = finish(d, src, yr, lab, "legacy")
    else:
        d, src = read_new(yr, lab, *NEW[(yr, lab)])
        d, msg = finish(d, src, yr, lab, "updated")
    OUT.mkdir(parents=True, exist_ok=True)
    d.to_parquet(OUT / f"asec_{yr}_{lab}.parquet", index=False, compression="zstd")
    return msg


if __name__ == "__main__" and ONLY == {0}:   # layout check only: canonical items each dictionary lacks
    for (yr, lab), (url, dname) in LEGACY.items():
        lay = parse_dct(fetch(f"{NBER}/data/progs/cps/{dname}.dct", "nber_" + dname + ".dct"))
        print(yr, lab, sorted(set(PERSON) - set(pick(lay["p"], PERSON))), sorted(set(HOUSE) - set(pick(lay["h"], HOUSE))))
elif __name__ == "__main__":
    tasks = [(k, "legacy") for k in LEGACY] + [(k, "new") for k in NEW]
    tasks = [t for t in tasks if not ONLY or t[0][0] in ONLY]
    with Pool(2) as pool:
        for m in pool.imap(run, tasks):
            print(m, flush=True)
