"""Aggregate checks of the PSID family-year panel; writes only aggregate tables to psid/output/.

Usage: python3 -I psid/scripts/validate.py [PANEL_DIR]   (default /mnt/project-files/psid)
Outputs (all counts, means, medians by year/group; no person-level data):
  output/validation_by_year.csv  heads, weighted/unweighted mean and median head labor income, share positive,
                                 mean age, share married, by survey year and sample group
  output/cps_compare.csv         male heads 25-60: PSID head labor income vs CPS ASEC pearnval of male householders
  output/cgm_components.csv      which components enter cgm_inc each year, and component means
  output/sentinel_counts.csv     heads with a missing-data code or top/bottom code, by year and concept
  output/cgm_sample_check.csv    counts of a CGM-style estimation sample (SRC male heads 20-65, 1970-1992) vs CGM Table 1
  output/jumps.csv               year-to-year changes in PSID means relative to CPS, flagged when large
  output/break_1994_check.csv    share of heads 25-60 with zero head labor income by year, PSID definition vs the
                                 consistent definition (farm and business labor income added back from 1994)
  output/annualize_check.csv     1994-2003 annualized transfers (_ann, _full) vs PSID-generated annual amounts in
                                 1985-1993 and 2005-2009: recipients, mean and median per recipient head
"""
import os, sys, glob, collections
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PSID = os.path.dirname(HERE)
REPO = os.path.dirname(PSID)
OUT = os.path.join(PSID, "output")


def wquant(x, w, q=0.5):
    m = ~(np.isnan(x) | np.isnan(w)) & (w > 0)
    x, w = x[m], w[m]
    if len(x) == 0: return np.nan
    o = np.argsort(x); x, w = x[o], w[o]
    c = np.cumsum(w) / w.sum()
    return float(x[np.searchsorted(c, q)])


def wmean(x, w):
    m = ~(np.isnan(x) | np.isnan(w)) & (w > 0)
    return float(np.average(x[m], weights=w[m])) if m.any() else np.nan


def summarize(d):
    x = d["labinc_h"].to_numpy(float); w = d["fam_weight"].to_numpy(float)
    return pd.Series({
        "n_heads": len(d), "n_weight_pos": int((w > 0).sum()), "sum_weight": round(np.nansum(w), 1),
        "labinc_h_mean": round(np.nanmean(x), 0), "labinc_h_median": round(np.nanmedian(x), 0),
        "labinc_h_wmean": round(wmean(x, w), 0), "labinc_h_wmedian": round(wquant(x, w), 0),
        "share_labinc_pos": round(np.nanmean(x > 0) if np.isfinite(x).any() else np.nan, 4),
        "wshare_labinc_pos": round(wmean((x > 0).astype(float) + np.where(np.isnan(x), np.nan, 0), w), 4),
        "n_labinc_missing": int(np.isnan(x).sum()),
        "age_h_mean": round(d["age_h"].mean(), 2), "share_married": round(d["married"].mean(), 4),
        "wshare_married": round(wmean(d["married"].to_numpy(float), w), 4),
        "share_male_head": round((d["sex_h"] == 1).mean(), 4),
        "cgm_inc_wmean": round(wmean(d["cgm_inc"].to_numpy(float), w), 0),
        "labinc_h_modal_pos_value": (x[x > 0].size and pd.Series(x[x > 0]).mode().iloc[0]) or np.nan,
        "share_pos_at_modal_value": round(pd.Series(x[x > 0]).value_counts(normalize=True).iloc[0], 4)
                                    if (x > 0).any() else np.nan,
    })


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/mnt/project-files/psid"
    F = pd.read_parquet(os.path.join(src, "psid_family_year.parquet"))
    os.makedirs(OUT, exist_ok=True)
    groups = {"all": F, "core_SRC_SEO": F[F["sample"].isin(["SRC", "SEO"])], "SRC": F[F["sample"] == "SRC"]}
    tabs = []
    for g, d in groups.items():
        t = d.groupby("year").apply(summarize, include_groups=False).reset_index()
        t.insert(1, "group", g); tabs.append(t)
    V = pd.concat(tabs).sort_values(["group", "year"])
    V.to_csv(os.path.join(OUT, "validation_by_year.csv"), index=False)

    # ---- CPS comparison: male heads / householders aged 25-60, nominal mean annual earnings
    cps = []
    for p in sorted(glob.glob(os.path.join(REPO, "cps", "data", "asec_*_production.parquet"))):
        c = pd.read_parquet(p, columns=["asec_year", "income_year", "a_exprrp", "sex", "age", "pearnval", "marsupwt"])
        c = c[c["a_exprrp"].isin([1, 2]) & (c["sex"] == 1) & c["age"].between(25, 60)]
        e = c["pearnval"].to_numpy(float); w = c["marsupwt"].to_numpy(float)
        cps.append(dict(income_year=int(c["income_year"].iloc[0]), cps_n=len(c), cps_mean=round(wmean(e, w), 0),
                        cps_median=round(wquant(e, w), 0), cps_share_pos=round(wmean((e > 0).astype(float), w), 4),
                        cps_mean_pos=round(wmean(e[e > 0], w[e > 0]), 0)))
    C = pd.DataFrame(cps)
    M = F[(F["sex_h"] == 1) & F["age_h"].between(25, 60) & (F["fam_weight"] > 0)]
    rows = []
    for (y, iy), d in M.groupby(["year", "income_year"]):
        x = d["labinc_h"].to_numpy(float); w = d["fam_weight"].to_numpy(float)
        core = d[d["sample"].isin(["SRC", "SEO"])]
        rows.append(dict(year=y, income_year=iy, psid_n=len(d), psid_wmean=round(wmean(x, w), 0),
                         psid_wmedian=round(wquant(x, w), 0), psid_wshare_pos=round(wmean((x > 0).astype(float), w), 4),
                         psid_wmean_pos=round(wmean(x[x > 0], w[x > 0]), 0),
                         psid_core_wmean=round(wmean(core["labinc_h"].to_numpy(float), core["fam_weight"].to_numpy(float)), 0)))
    Pm = pd.DataFrame(rows).merge(C, on="income_year", how="left")
    Pm["ratio_mean"] = (Pm["psid_wmean"] / Pm["cps_mean"]).round(3)
    Pm["ratio_median"] = (Pm["psid_wmedian"] / Pm["cps_median"]).round(3)
    Pm["ratio_mean_pos"] = (Pm["psid_wmean_pos"] / Pm["cps_mean_pos"]).round(3)
    Pm.to_csv(os.path.join(OUT, "cps_compare.csv"), index=False)

    # ---- jumps: annualized log change of PSID weighted mean minus same for CPS (where both exist)
    a = V[V["group"] == "all"][["year", "n_heads", "labinc_h_wmean", "labinc_h_wmedian", "age_h_mean",
                                "share_married"]].reset_index(drop=True)
    a["gap"] = a["year"].diff()
    a["dlog_wmean_pa"] = (np.log(a["labinc_h_wmean"]).diff() / a["gap"]).round(4)
    a["dlog_n_heads"] = np.log(a["n_heads"]).diff().round(3)
    a["d_age"] = a["age_h_mean"].diff().round(2); a["d_married"] = a["share_married"].diff().round(4)
    c2 = Pm[["year", "psid_wmean", "cps_mean"]].copy(); c2["gap"] = c2["year"].diff()
    c2["dlog_psid_male2560_pa"] = (np.log(c2["psid_wmean"]).diff() / c2["gap"]).round(4)
    c2["dlog_cps_male2560_pa"] = (np.log(c2["cps_mean"]).diff() / c2["gap"]).round(4)
    J = a.merge(c2[["year", "dlog_psid_male2560_pa", "dlog_cps_male2560_pa"]], on="year", how="left")
    J["excess_vs_cps"] = (J["dlog_psid_male2560_pa"] - J["dlog_cps_male2560_pa"]).round(4)
    J["flag"] = np.where((J["dlog_n_heads"].abs() > 0.1) | (J["excess_vs_cps"].abs() > 0.04) |
                         (J["d_age"].abs() > 0.8), "check", "")
    J.to_csv(os.path.join(OUT, "jumps.csv"), index=False)

    # ---- CGM components by year
    comp_cols = ["labinc_h", "labinc_w", "ucwc_h", "unemp_h", "wcomp_h", "unemp_w", "wcomp_w", "ss_h", "ss_w",
                 "ss_hw", "ss_fam", "ssi_hw", "ssi_h", "ssi_w", "welf_h", "welf_hw", "welf_w", "chsup_h",
                 "chsup_hw", "chsup_w", "help_h_bktmid", "help_h", "help_w"]
    rows = []
    for y, d in F.groupby("year"):
        r = dict(year=y, income_year=y - 1, components=d["cgm_components"].iloc[0], missing=d["cgm_missing"].iloc[0],
                 cgm_inc_mean=round(d["cgm_inc"].mean(), 0), cgm_inc_n_zero=int((d["cgm_inc"] == 0).sum()),
                 cgm_inc_n_nonpos=int((d["cgm_inc"] <= 0).sum()), cgm_inc_n_missing=int(d["cgm_inc"].isna().sum()))
        for c in comp_cols:
            if c in d and d[c].notna().any(): r[f"mean_{c}"] = round(d[c].mean(), 0)
        rows.append(r)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "cgm_components.csv"), index=False)

    # ---- CGM (2005) sample check: SRC male heads 20-65 (22-65 college), survey years 1970-1992, not retired
    # (1968-1975: retired or disabled), housewife or student, positive cgm_inc; unit = head x education group
    S = F[(F["sample"] == "SRC") & (F["sex_h"] == 1) & F["year"].between(1970, 1992) & F["age_h"].between(20, 65)
          & ~F["emp_h8"].isin([4, 6, 7]) & F["educ3_h"].notna()]
    n_nonpos = int((S["cgm_inc"] <= 0).sum()); n_all = len(S)
    S = S[(S["cgm_inc"] > 0) & ~((S["educ3_h"] == 3) & (S["age_h"] < 22))]
    unit = S["pid68_h"].astype(str) + "_" + S["pn_h"].astype(str) + "_" + S["educ3_h"].astype(int).astype(str)
    g = S.assign(unit=unit).groupby("educ3_h")
    K = pd.DataFrame({"obs": g.size(), "units": g["unit"].nunique()})
    K["Tbar"] = (K["obs"] / K["units"]).round(2)
    K.index = K.index.map({1.0: "no_high_school", 2.0: "high_school", 3.0: "college"})
    K["cgm_units"] = [1104, 2816, 1110]; K["cgm_Tbar"] = [8.58, 9.57, 11.06]
    K["share_nonpositive_dropped"] = round(n_nonpos / n_all, 5); K["cgm_share_zero_dropped"] = 0.00495
    K.reset_index(names="educ_group").to_csv(os.path.join(OUT, "cgm_sample_check.csv"), index=False)

    # ---- 1994 break: share of heads with zero labor income, PSID definition vs consistent (farm + business added)
    rows = []
    base = F[F["age_h"].between(25, 60) & F["year"].between(1985, 2023)]
    for gname, d0 in (("male_heads_25_60", base[base["sex_h"] == 1]),
                      ("male_heads_25_60_SRC_SEO", base[(base["sex_h"] == 1) & base["sample"].isin(["SRC", "SEO"])]),
                      ("male_heads_25_60_hours_pos", base[(base["sex_h"] == 1) & (base["hours_h"] > 0)]),
                      ("all_heads_25_60", base)):
        for y, d in d0.groupby("year"):
            w = d["fam_weight"].to_numpy(float)
            r = dict(group=gname, year=y, n=len(d))
            for nm, c in (("psid", "labinc_h"), ("cons", "labinc_h_cons")):
                x = d[c].to_numpy(float); ok = ~np.isnan(x)
                r[f"zero_share_{nm}"] = round(float((x[ok] == 0).mean()), 4)
                r[f"wzero_share_{nm}"] = round(wmean(np.where(ok, (x == 0).astype(float), np.nan), w), 4)
                r[f"wmean_{nm}"] = round(wmean(x, w), 0)
                r[f"n_missing_{nm}"] = int((~ok).sum())
            for nm, c in (("psid", "cgm_inc_psiddef"), ("cons", "cgm_inc")):
                x = d[c].to_numpy(float); ok = ~np.isnan(x)
                r[f"cgm_nonpos_share_{nm}"] = round(float((x[ok] <= 0).mean()), 4)
            r["n_farmlab_pos"] = int((d["farmlab_h"] > 0).sum()); r["n_buslab_h_pos"] = int((d["buslab_h"] > 0).sum())
            rows.append(r)
    B = pd.DataFrame(rows)
    B.to_csv(os.path.join(OUT, "break_1994_check.csv"), index=False)
    m = B[B["group"] == "male_heads_25_60"].set_index("year")
    pre, post_p, post_c = m.loc[1993, "zero_share_psid"], m.loc[1994, "zero_share_psid"], m.loc[1994, "zero_share_cons"]
    status = "CLOSED" if abs(post_c - pre) <= 0.01 else "NOT CLOSED"
    print(f"1994 break check (male heads 25-60, zero head labor income): 1993 {pre:.3f}; 1994 PSID {post_p:.3f}, "
          f"consistent {post_c:.3f} -> {status} (tolerance 1 point)")

    # ---- annualized 1994-2003 transfers vs PSID-generated annual amounts in 1985-1993 and 2005-2009
    rows = []
    items = ["unemp_h", "wcomp_h", "unemp_w", "wcomp_w", "ssi_h", "ssi_w", "welf_h", "welf_w", "chsup_h", "chsup_w",
             "help_h", "help_w", "adc_h", "adc_w"]
    for k in items:
        for y, d in F[F["year"].between(1985, 2009)].groupby("year"):
            r = dict(item=k, year=y, n_heads=len(d))
            if 1994 <= y <= 2003:
                a = d[k + "_rep"]; r["n_recipients"] = int((a > 0).sum()); r["n_amount_missing"] = int(a.isna().sum())
                r["n_unit_assumed_year"] = int(d["ann_flags"].str.contains(k + ":unit_assumed").sum())
                r["n_unit_implausible"] = int(d["ann_flags"].str.contains(k + ":unit_implausible").sum())
                for v in ("ann", "full"):
                    x = d[f"{k}_{v}"]; r[f"mean_per_recipient_{v}"] = round(x[x > 0].mean(), 0)
                    r[f"median_per_recipient_{v}"] = round(x[x > 0].median(), 0)
                r["mean_per_recipient_rep"] = round(a[a > 0].mean(), 0)
                r["source"] = "annualized"
            elif k in d and d[k].notna().any():
                x = d[k]; r["n_recipients"] = int((x > 0).sum()); r["n_amount_missing"] = int(x.isna().sum())
                r["mean_per_recipient_generated"] = round(x[x > 0].mean(), 0)
                r["median_per_recipient_generated"] = round(x[x > 0].median(), 0)
                r["source"] = "psid_generated"
            else:
                continue
            rows.append(r)
    A = pd.DataFrame(rows)
    A.to_csv(os.path.join(OUT, "annualize_check.csv"), index=False)

    # ---- sentinel / top-code counts
    cnt = collections.Counter()
    for col, kind in (("na_flags", "missing_code"), ("tc_flags", "top_or_bottom_code")):
        for y, s in zip(F["year"], F[col]):
            for t in s.split(";"):
                if t: cnt[(y, t, kind)] += 1
    S = pd.DataFrame([dict(year=y, concept=c, kind=k, n_heads=n) for (y, c, k), n in cnt.items()])
    S.sort_values(["kind", "concept", "year"]).to_csv(os.path.join(OUT, "sentinel_counts.csv"), index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
    print(V[V["group"] == "all"].drop(columns="group").to_string(index=False))
    print(Pm[["year", "psid_n", "psid_wmean", "cps_mean", "ratio_mean", "psid_wmedian", "cps_median", "ratio_median",
              "psid_wshare_pos", "cps_share_pos"]].to_string(index=False))
    print(J[J["flag"] != ""].to_string(index=False))
    print(K.to_string())


if __name__ == "__main__":
    main()
