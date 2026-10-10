"""Build the PSID family-year and person-year panels from two PSID Data Center extracts.

Usage: python3 -I psid/scripts/build.py RAW_DIR1 RAW_DIR2 [OUT_DIR]
  RAW_DIR1 holds J366052.txt/.do (first extract: state, transfers, year of birth)
  RAW_DIR2 holds J366057.txt/.do (main extract)
  OUT_DIR  defaults to /mnt/project-files/psid (person-level output; never inside the repo)

Reads psid/varmap.csv (year x concept -> variable, with missing-data and top codes copied from the codebooks)
and writes OUT_DIR/psid_family_year.parquet and OUT_DIR/psid_person_year.parquet. All amounts nominal.
Aggregate checks go to psid/output via validate.py.
"""
import os, re, sys, csv
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PSID = os.path.dirname(HERE)
YEARS = list(range(1968, 1998)) + list(range(1999, 2024, 2))
MONEY = ["labinc_h", "labinc_w", "wages_h", "wages_w", "taxable_hw", "faminc", "ucwc_h", "unemp_h", "wcomp_h",
         "unemp_w", "wcomp_w", "ss_h", "ss_w", "ss_hw", "ss_fam", "ssi_hw", "ssi_h", "ssi_w", "welf_h", "welf_hw",
         "welf_w", "chsup_h", "chsup_hw", "chsup_w", "help_h", "help_w"]
REPORTED = ["unemp_h_rep", "wcomp_h_rep", "unemp_w_rep", "wcomp_w_rep", "ssi_h_rep", "ssi_w_rep", "welf_h_rep",
            "welf_w_rep", "chsup_h_rep", "chsup_w_rep", "help_h_rep", "help_w_rep"]
CATEG_ZERO_NA = ["occ_h", "occ_h_orig", "indus_h", "indus_h_orig", "occ_w"]  # 0 = inapplicable
BKT_MID = {0: 0, 1: 250, 2: 750, 3: 1500, 4: 2500, 5: 4000, 6: 6250, 7: 8750, 8: 10000}  # $ bracket midpoints
BKT_EDUC_YRS = {0: 4, 1: 4, 2: 7, 3: 10, 4: 12, 5: 12, 6: 14, 7: 16, 8: 17}  # bracket -> grades


def infix(do_path):
    txt = open(do_path, encoding="latin-1").read()
    body = txt[txt.index("infix"):txt.index("using")]
    return {v.upper(): (int(a), int(b)) for v, a, b in re.findall(r"(\w+)\s+(\d+)\s*-\s*(\d+)", body)}


class Extract:
    """Fixed-width file held as a uint8 matrix; columns parsed on demand."""
    def __init__(self, txt_path, do_path):
        self.pos = infix(do_path)
        reclen = max(b for a, b in self.pos.values())
        raw = np.fromfile(txt_path, dtype=np.uint8)
        nl = 2 if raw[reclen] == 13 else 1
        self.m = raw.reshape(-1, reclen + nl)
        assert (self.m[:, reclen + nl - 1] == 10).all(), "unexpected record layout"
        self.n = self.m.shape[0]
        self.cache = {}

    def get(self, v):
        if v not in self.cache:
            a, b = self.pos[v]
            sub = np.ascontiguousarray(self.m[:, a - 1:b])
            blank = (sub == 32).all(axis=1)
            s = sub.view(f"S{b - a + 1}").ravel().copy()
            s[blank] = b"0"
            x = s.astype(np.float64)
            x[blank] = np.nan
            self.cache[v] = x
        return self.cache[v]


def load_map():
    rows = list(csv.DictReader(open(os.path.join(PSID, "varmap.csv"))))
    def nums(s): return [float(x) for x in s.split()] if s else []
    vm = {}
    for r in rows:
        y = int(r["year"]) if r["year"] else None
        vm[(y, r["concept"])] = dict(var=r["var"], job=r["job"], na=nums(r["na_codes"]),
                                     top=float(r["top_code"]) if r["top_code"] else None,
                                     bot=float(r["bottom_code"]) if r["bottom_code"] else None)
    return vm


def main():
    raw1, raw2 = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "/mnt/project-files/psid"
    os.makedirs(out, exist_ok=True)
    X = {"366052": Extract(os.path.join(raw1, "J366052.txt"), os.path.join(raw1, "J366052.do")),
         "366057": Extract(os.path.join(raw2, "J366057.txt"), os.path.join(raw2, "J366057.do"))}
    a, b = X["366052"], X["366057"]
    assert a.n == b.n == 85536, (a.n, b.n)
    for v in ("ER30001", "ER30002"):
        assert np.array_equal(a.get(v), b.get(v)), f"row order differs on {v}"
    print(f"{b.n} individuals; row order of both extracts matches on ER30001/ER30002")
    vm = load_map()

    def raw(y, c):
        e = vm.get((y, c))
        return None if e is None else X[e["job"]].get(e["var"])

    def clean(y, c, idx):
        """Values of concept c in year y for rows idx: sentinels -> NaN. Returns (values, na_flag, tc_flag)."""
        e = vm.get((y, c))
        n = len(idx)
        if e is None:
            return np.full(n, np.nan), np.zeros(n, bool), np.zeros(n, bool)
        x = X[e["job"]].get(e["var"])[idx].copy()
        na = np.isin(x, e["na"]) if e["na"] else np.zeros(n, bool)
        tc = np.zeros(n, bool)
        if c in MONEY or c in REPORTED:
            if e["top"] is not None: tc |= x == e["top"]
            if e["bot"] is not None: tc |= x == e["bot"]
        x[na] = np.nan
        if c in CATEG_ZERO_NA: x[x == 0] = np.nan
        return x, na, tc

    pid68 = b.get("ER30001").astype(np.int64); pn = b.get("ER30002").astype(np.int64)
    sex_ind = b.get("ER32000"); samp_status = b.get("ER32006")

    # ---------- year of birth: modal valid report across waves (1988+), else age-based later
    yobs = []
    for y in YEARS:
        r = raw(y, "ind_yob")
        if r is not None:
            yobs.append(np.where((r >= 1870) & (r <= 2025), r, np.nan))
    Y = np.vstack(yobs).T
    yob_mode = pd.DataFrame(Y).mode(axis=1, dropna=True)
    yob_rep = yob_mode[0].to_numpy() if yob_mode.shape[1] else np.full(b.n, np.nan)
    yob_nvals = pd.DataFrame(Y).nunique(axis=1).to_numpy()

    fam_rows, per_rows, log = [], [], []
    for y in YEARS:
        intv = raw(y, "ind_interview"); rel = raw(y, "ind_rel")
        seq = raw(y, "ind_seq")
        if y == 1968:
            in_fu = (intv > 0) & (rel > 0)
            seqv = np.where(in_fu, 1.0, 0.0)  # no sequence number in 1968
        else:
            in_fu = (intv > 0) & (seq >= 1) & (seq <= 20)
            seqv = seq
        is_head = in_fu & np.isin(rel, [1, 10]) & ((seqv == 1) if y > 1968 else True)
        is_sp = in_fu & np.isin(rel, [2, 20, 22])
        # ----- person-year
        P = np.flatnonzero(in_fu)
        age_i = raw(y, "ind_age")[P].copy(); age_i[(age_i == 999) | (age_i == 0)] = np.nan
        ed = raw(y, "ind_educ"); ed_i = ed[P].copy() if ed is not None else np.full(len(P), np.nan)
        if ed is not None: ed_i[(ed_i == 0) | (ed_i >= 98)] = np.nan
        em = raw(y, "ind_emp"); em_i = em[P].copy() if em is not None else np.full(len(P), np.nan)
        if em is not None: em_i[(em_i == 0) | (em_i == 9)] = np.nan
        fw_all = raw(y, "fam_weight")
        per_rows.append(pd.DataFrame({
            "pid68": pid68[P], "pn": pn[P], "year": y, "interview": intv[P].astype(np.int64),
            "seq": seqv[P].astype(np.int64), "rel": rel[P].astype(np.int64),
            "is_head": is_head[P], "is_spouse": is_sp[P], "age": age_i, "educ_yrs": ed_i, "emp": em_i,
            "sex": sex_ind[P], "yob": yob_rep[P], "sample_status": samp_status[P], "fam_weight": fw_all[P]}))
        # ----- heads and spouses
        H = np.flatnonzero(is_head)
        fam_ids = intv[H]
        u, cnt = np.unique(fam_ids, return_counts=True)
        n_fams = len(np.unique(intv[in_fu]))
        log.append(f"{y}: {len(H)} heads, {n_fams} families with members in FU, "
                   f"{(cnt > 1).sum()} families with >1 head")
        S = np.flatnonzero(is_sp)
        sp = pd.DataFrame({"interview": intv[S], "sp_idx": S}).drop_duplicates("interview", keep=False)
        n_multi = len(S) - len(sp)
        if n_multi: log.append(f"{y}: {n_multi} spouse rows in families with >1 spouse (dropped)")
        d = pd.DataFrame({"interview": fam_ids, "h_idx": H}).merge(sp, on="interview", how="left")
        H = d["h_idx"].to_numpy(); Sx = d["sp_idx"].to_numpy()
        has_sp = ~np.isnan(Sx); Si = np.where(has_sp, Sx, 0).astype(np.int64)
        f = pd.DataFrame({"year": y, "income_year": y - 1, "fid": d["interview"].astype(np.int64),
                          "pid68_h": pid68[H], "pn_h": pn[H],
                          "pid68_sp": np.where(has_sp, pid68[Si], -1), "pn_sp": np.where(has_sp, pn[Si], -1),
                          "rel_sp": np.where(has_sp, rel[Si], np.nan)})
        flags_na, flags_tc = [], []
        concepts = sorted({c for (yy, c) in vm if yy == y})
        for c in concepts:
            if c.startswith("ind_"): continue
            x, na, tc = clean(y, c, H)
            if c == "fid":
                bad = int((x != f["fid"].to_numpy()).sum())
                if bad: log.append(f"{y}: {bad} heads whose family-file interview number differs from the individual file")
                continue
            f[c] = x
            if na.any(): flags_na.append(np.where(na, c, ""))
            if tc.any(): flags_tc.append(np.where(tc, c, ""))
        def joinflags(lst):
            if not lst: return np.full(len(H), "", dtype=object)
            arr = np.vstack(lst).T
            return np.array([";".join(t for t in r if t) for r in arr], dtype=object)
        f["na_flags"] = joinflags(flags_na); f["tc_flags"] = joinflags(flags_tc)
        # individual-file items for head and spouse
        ia = raw(y, "ind_age"); f["age_h_ind"] = ia[H]; f["age_sp_ind"] = np.where(has_sp, ia[Si], np.nan)
        f["educ_h_ind"] = ed[H] if ed is not None else np.nan
        f["educ_sp_ind"] = np.where(has_sp, ed[Si], np.nan) if ed is not None else np.nan
        f["emp_h_ind"] = em[H] if em is not None else np.nan
        f["emp_sp_ind"] = np.where(has_sp, em[Si], np.nan) if em is not None else np.nan
        f["sex_h_ind"] = sex_ind[H]
        f["yob_h_rep"] = yob_rep[H]; f["yob_h_nvals"] = yob_nvals[H]
        f["yob_sp_rep"] = np.where(has_sp, yob_rep[Si], np.nan)
        fam_rows.append(f)
    print("\n".join(log))
    F = pd.concat(fam_rows, ignore_index=True)
    P = pd.concat(per_rows, ignore_index=True)
    F = derive(F)
    P = derive_person(P, F)
    F.to_parquet(os.path.join(out, "psid_family_year.parquet"), index=False)
    P.to_parquet(os.path.join(out, "psid_person_year.parquet"), index=False)
    print(f"family-year rows {len(F)}, columns {F.shape[1]}; person-year rows {len(P)}")


def sample_of(pid68):
    return np.select([pid68 < 3000, (pid68 >= 5001) & (pid68 <= 6872), (pid68 >= 3001) & (pid68 <= 3511),
                      (pid68 >= 4001) & (pid68 <= 4851), (pid68 >= 7001) & (pid68 <= 9308)],
                     ["SRC", "SEO", "IMM9799", "IMM1719", "LATINO"], "OTHER")


def educ_years(yrs, ind, bkt):
    """Years of schooling from family-file years, individual-file years, then bracket; returns (years, source)."""
    yrs = np.where((yrs >= 0) & (yrs <= 17), yrs, np.nan)
    ind = np.where((ind >= 1) & (ind <= 17), ind, np.nan)
    bk = pd.Series(np.where((bkt >= 0) & (bkt <= 8), bkt, np.nan)).map(BKT_EDUC_YRS).to_numpy(dtype=float)
    out = np.where(~np.isnan(yrs), yrs, np.where(~np.isnan(ind), ind, bk))
    src = np.select([~np.isnan(yrs), ~np.isnan(ind), ~np.isnan(bk)], ["fam_yrs", "ind_yrs", "fam_bkt"], "")
    return out, src


def educ_groups(yrs):
    g4 = np.select([yrs < 12, yrs == 12, (yrs > 12) & (yrs < 16), yrs >= 16], [1, 2, 3, 4], 0).astype(float)
    g4[np.isnan(yrs)] = np.nan
    g3 = np.select([yrs < 12, (yrs >= 12) & (yrs < 16), yrs >= 16], [1, 2, 3], 0).astype(float)
    g3[np.isnan(yrs)] = np.nan
    return g4, g3


def derive(F):
    y = F["year"].to_numpy()
    has_sp = (F["pid68_sp"] > 0).to_numpy()
    F["sample"] = sample_of(F["pid68_h"].to_numpy())
    F["weight_series"] = np.select([y <= 1992, y <= 1996], ["core_1968_1992", "core_revised_1993_1996"],
                                   "core_immigrant_1997_2023")
    F["spouse_present"] = has_sp
    F["married"] = has_sp.astype(float)
    # ages: family file first, individual file as fallback
    F.loc[F["age_w"] == 0, "age_w"] = np.nan
    F["age_sp"] = np.where(has_sp, F["age_w"].fillna(F["age_sp_ind"].where(F["age_sp_ind"].between(1, 125))), np.nan)
    F["age_h"] = F["age_h"].fillna(F["age_h_ind"].where(F["age_h_ind"].between(1, 125)))
    F["sex_h"] = F["sex_h"].where(F["sex_h"].isin([1, 2]), F["sex_h_ind"].where(F["sex_h_ind"].isin([1, 2])))
    # education
    yrs, src = educ_years(F["educ_h_yrs"].to_numpy(), F["educ_h_ind"].to_numpy(), F["educ_h_bkt"].to_numpy())
    F["educ_yrs_h"], F["educ_src_h"] = yrs, src
    F["educ4_h"], F["educ3_h"] = educ_groups(yrs)
    wy = F["educ_w_yrs"].where(has_sp).to_numpy(); wb = F["educ_w_bkt"].where(has_sp).to_numpy()
    wy = np.where(wy == 0, np.nan, wy)  # 0 mixes 'none' and 'no wife'; few wives have 0 grades
    wb = np.where(wb == 0, np.nan, wb)
    yrs, src = educ_years(wy, F["educ_sp_ind"].where(has_sp).to_numpy(), wb)
    F["educ_yrs_sp"], F["educ_src_sp"] = yrs, src
    F["educ4_sp"], F["educ3_sp"] = educ_groups(yrs)
    # person-level education of the head: mode of wave values at age 25+, ties -> higher
    t = F.loc[F["age_h"] >= 25, ["pid68_h", "pn_h", "educ_yrs_h"]].dropna()
    md = (t.groupby(["pid68_h", "pn_h", "educ_yrs_h"]).size().rename("k").reset_index()
          .sort_values(["pid68_h", "pn_h", "k", "educ_yrs_h"]).groupby(["pid68_h", "pn_h"]).tail(1))
    F = F.merge(md.rename(columns={"educ_yrs_h": "educ_yrs_h_p"})[["pid68_h", "pn_h", "educ_yrs_h_p"]],
                on=["pid68_h", "pn_h"], how="left")
    F["educ4_h_p"], F["educ3_h_p"] = educ_groups(F["educ_yrs_h_p"].to_numpy())
    # employment status of head, harmonized to the 1976+ 8 codes
    e = F["emp_h"].to_numpy(); y = F["year"].to_numpy()
    early = y <= 1975
    e8 = np.where(early, pd.Series(e).map({1: 1, 2: 3, 3: 4, 4: 6, 5: 7, 6: 8}).to_numpy(dtype=float), e)
    e8 = np.where((e8 >= 1) & (e8 <= 8), e8, np.nan)
    F["emp_h8"] = e8
    F["emp_scheme"] = np.where(early, "6cat_1968_1975_ret_and_disabled_in_4", "8cat")
    F["emp_h3"] = np.select([np.isin(e8, [1, 2]), e8 == 3, np.isin(e8, [4, 5, 6, 7, 8])], [1, 2, 3], 0).astype(float)
    F.loc[np.isnan(e8), "emp_h3"] = np.nan
    # code vintages for occupation / industry
    F["occ_vint"] = np.select([y <= 1980, y <= 2001, y <= 2015], ["census1970_3d_retro", "census1970_3d",
                              "census2000_3d"], "census2010_4d")
    F["indus_vint"] = np.select([y <= 1980, y <= 2001, y <= 2015], ["census1970_3d_retro", "census1970_3d",
                              "census2000_3d"], "census2012_4d")
    F["occ_orig_vint"] = np.select([y == 1974, y <= 1975, y <= 1980], ["census1970_3d", "psid_1d", "psid_2d"], "")
    F.loc[F["occ_h_orig"].isna(), "occ_orig_vint"] = ""
    F["indus_orig_vint"] = np.where(F["indus_h_orig"].notna(), "psid_2d", "")
    # birth year
    F["yob_h"] = F["yob_h_rep"].fillna(F["year"] - F["age_h"])
    F["yob_src_h"] = np.where(F["yob_h_rep"].notna(), "reported", np.where(F["age_h"].notna(), "year_minus_age", ""))
    # help from relatives: bracket midpoints 1968-1975
    hb = F["help_h_bkt"].to_numpy()
    F["help_h_bktmid"] = pd.Series(np.where((hb >= 0) & (hb <= 8), hb, np.nan)).map(BKT_MID).to_numpy(dtype=float)
    F = cgm_income(F)
    F["labinc_hw"] = F["labinc_h"] + F["labinc_w"].fillna(0)
    drop = ["educ_h_ind", "educ_sp_ind", "age_h_ind", "age_sp_ind", "sex_h_ind", "yob_h_rep"]
    F = F.drop(columns=drop)
    first = ["year", "income_year", "fid", "pid68_h", "pn_h", "pid68_sp", "pn_sp", "rel_sp", "sample",
             "fam_weight", "weight_series", "age_h", "sex_h", "yob_h", "yob_src_h", "married", "spouse_present",
             "marital_h", "marital_gen", "age_sp", "educ_yrs_h", "educ4_h", "educ3_h", "educ_src_h", "educ_yrs_h_p",
             "educ4_h_p", "educ3_h_p", "educ_yrs_sp", "educ4_sp", "educ3_sp", "educ_src_sp", "fu_size", "n_children",
             "labinc_h", "labinc_w", "labinc_hw", "cgm_inc", "cgm_components", "cgm_missing"]
    last = ["na_flags", "tc_flags"]
    rest = sorted(c for c in F.columns if c not in first + last)
    return F[first + rest + last].sort_values(["year", "fid"]).reset_index(drop=True)


def cgm_income(F):
    """CGM (2005) labor income: head + spouse labor income + unemployment + workers comp + Social Security + SSI +
    other welfare + child support + help from relatives, using whatever the extracts carry in each year."""
    y = F["year"].to_numpy()
    z = lambda c: F[c] if c in F else pd.Series(np.nan, index=F.index)
    def s(*cs):  # sum of columns that exist for the row's year, NaN if any of them is NaN
        out = pd.Series(0.0, index=F.index)
        for c in cs: out = out + z(c)
        return out
    comp = {}
    comp["lab"] = (s("labinc_h") + z("labinc_w").fillna(0), np.full(len(F), "labinc_h+labinc_w"))
    ucwc = np.select([(y >= 1970) & (y <= 1976), (y >= 1977) & (y <= 1984), ((y >= 1985) & (y <= 1993)) | (y >= 2005)],
                     [z("ucwc_h"), s("unemp_h", "wcomp_h"), s("unemp_h", "wcomp_h", "unemp_w", "wcomp_w")], 0.0)
    ucwc_l = np.select([(y >= 1970) & (y <= 1976), (y >= 1977) & (y <= 1984), ((y >= 1985) & (y <= 1993)) | (y >= 2005)],
                       ["ucwc_h", "unemp_h+wcomp_h", "unemp_hw+wcomp_hw"], "")
    ss = np.select([y == 1970, (y >= 1971) & (y <= 1985), ((y >= 1986) & (y <= 1993)) | (y >= 2005),
                    (y >= 1994) & (y <= 2003)], [z("ss_h"), z("ss_hw"), s("ss_h", "ss_w"), z("ss_fam")], 0.0)
    ss_l = np.select([y == 1970, (y >= 1971) & (y <= 1985), ((y >= 1986) & (y <= 1993)) | (y >= 2005),
                      (y >= 1994) & (y <= 2003)], ["ss_h", "ss_hw", "ss_h+ss_w", "ss_fam"], "")
    ssi = np.select([(y >= 1975) & (y <= 1985), ((y >= 1986) & (y <= 1993)) | (y >= 2005)],
                    [z("ssi_hw"), s("ssi_h", "ssi_w")], 0.0)
    ssi_l = np.select([(y >= 1975) & (y <= 1985), ((y >= 1986) & (y <= 1993)) | (y >= 2005)], ["ssi_hw", "ssi_h+ssi_w"], "")
    welf = np.select([y == 1970, (y >= 1971) & (y <= 1985), ((y >= 1986) & (y <= 1993)) | (y >= 2005)],
                     [z("welf_h"), z("welf_hw"), s("welf_h", "welf_w")], 0.0)
    welf_l = np.select([y == 1970, (y >= 1971) & (y <= 1985), ((y >= 1986) & (y <= 1993)) | (y >= 2005)],
                       ["welf_h", "welf_hw", "welf_h+welf_w"], "")
    cs = np.select([(y >= 1970) & (y <= 1975), (y >= 1976) & (y <= 1980), (y >= 1981) & (y <= 1984),
                    ((y >= 1985) & (y <= 1993)) | (y >= 2005)],
                   [z("chsup_h"), z("chsup_hw"), z("chsup_h"), s("chsup_h", "chsup_w")], 0.0)
    cs_l = np.select([(y >= 1970) & (y <= 1975), (y >= 1976) & (y <= 1980), (y >= 1981) & (y <= 1984),
                      ((y >= 1985) & (y <= 1993)) | (y >= 2005)],
                     ["chsup_h(incl_alimony)", "chsup_hw", "chsup_h", "chsup_h+chsup_w"], "")
    hp = np.select([y <= 1975, (y >= 1976) & (y <= 1984), ((y >= 1985) & (y <= 1993)) | (y >= 2005)],
                   [z("help_h_bktmid"), z("help_h"), s("help_h", "help_w")], 0.0)
    hp_l = np.select([y <= 1975, (y >= 1976) & (y <= 1984), ((y >= 1985) & (y <= 1993)) | (y >= 2005)],
                     ["help_h(bracket_midpoint)", "help_h", "help_h+help_w"], "")
    F["cgm_inc"] = comp["lab"][0].to_numpy() + ucwc + ss + ssi + welf + cs + hp
    labels = np.vstack([comp["lab"][1], ucwc_l, ss_l, ssi_l, welf_l, cs_l, hp_l]).T
    F["cgm_components"] = ["+".join(t for t in r if t) for r in labels]
    miss = []
    for yy in y:
        m = []
        if yy <= 1969: m += ["ucwc", "ss", "welfare", "child_support"]
        if 1970 <= yy <= 1984: m += ["ucwc_w"]
        if yy <= 1974: m += ["ssi(program from 1974)"]
        if 1970 <= yy <= 1984 and yy not in range(1976, 1981): m += ["chsup_w"]
        if yy <= 1984: m += ["help_w"]
        if yy == 1970: m += ["ss_w", "welf_w"]
        if 1994 <= yy <= 2003: m += ["ucwc_hw,ssi,welfare,child_support,help (only as-reported amounts)",
                                     "ss is family total"]
        if yy >= 1994: m += ["farm income and labor part of business income (not in labinc from 1994)"]
        miss.append(";".join(m))
    F["cgm_missing"] = miss
    return F


def derive_person(P, F):
    P["sample"] = sample_of(P["pid68"].to_numpy())
    P["rel_cat"] = np.select([P["rel"].isin([1, 10]), P["rel"].isin([2, 20, 22]),
                              ((P["year"] <= 1982) & (P["rel"] == 3)) | ((P["year"] >= 1983) & P["rel"].between(30, 38))],
                             ["head", "spouse", "child"], "other")
    P.loc[(P["year"] == 1968) & (P["rel"] == 3), "rel_cat"] = "child"
    return P.sort_values(["pid68", "pn", "year"]).reset_index(drop=True)


if __name__ == "__main__":
    main()
