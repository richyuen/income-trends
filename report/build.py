"""Step 4: build the report (one self-contained HTML page, inline SVG charts) from the step 2 and step 3 outputs.

Usage: python3 -I report/build.py     -> report/income_process_report.html
Reads only aggregate tables in the repo (cgm/output, extend/output, dataset/), so it runs without the PSID panel.
"""
import html
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "extend", "output")
CGM = os.path.join(ROOT, "cgm", "output")
OUTFILE = os.path.join(ROOT, "report", "income_process_report.html")

EDU = [("no_high_school", "No high school", "s1"), ("high_school", "High school", "s2"), ("college", "College", "s3")]
EDU_LABEL = {k: v for k, v, _ in EDU}
SECTOR_LABEL = {"agri_mining_construction": "Agriculture, mining, construction", "manufacturing": "Manufacturing",
                "trade": "Wholesale and retail trade", "transport_utilities_info": "Transport, utilities, information",
                "finance_business_services": "Finance and business services",
                "education_health_other_services": "Education, health, other services",
                "public_administration": "Public administration"}
PERIODS = [("p1", "1969-1980", "o1"), ("p2", "1981-1992", "o2"), ("p3", "1993-2006", "o3"), ("p4", "2007-2022", "o4")]

FIG = [0]
TAB = [0]


def esc(s):
    return html.escape(str(s), quote=True)


def f3(x):
    return "" if pd.isna(x) else f"{x:.3f}"


def f2(x):
    return "" if pd.isna(x) else f"{x:.2f}"


def tfmt(fmt, t):
    return fmt.format(0 if abs(t) < 1e-12 else t).replace("-0.", "0.") if abs(t) < 1e-12 else fmt.format(t)


def nice_ticks(lo, hi, n=5):
    span = hi - lo
    step = 10 ** np.floor(np.log10(span / n))
    for m in [1, 2, 2.5, 5, 10]:
        if span / (step * m) <= n:
            step *= m
            break
    t0 = np.ceil(lo / step - 1e-9) * step
    return [round(t, 10) for t in np.arange(t0, hi + step * 1e-6, step)]


# ------------------------------------------------------------------ chart primitives (inline SVG)
def line_chart(series, xlab, ylab, ydom=None, xdom=None, yfmt="{:.2f}", xfmt="{:.0f}", w=720, h=330, xticks=None,
               tipx="{:.0f}", label_ends=True, markers=False):
    """series: list of dict(name, cls, pts=[(x, y), ...], dash=False). Lines break at NaN."""
    ml, mr, mt, mb = 52, 150 if label_ends else 16, 14, 42
    xs = [x for s in series for x, y in s["pts"] if not pd.isna(y)]
    ys = [y for s in series for x, y in s["pts"] if not pd.isna(y)]
    x0, x1 = xdom or (min(xs), max(xs))
    if ydom is None:
        pad = (max(ys) - min(ys)) * 0.08 or 0.01
        ydom = (min(ys) - pad, max(ys) + pad)
    yt = nice_ticks(*ydom)
    y0, y1 = min(ydom[0], yt[0]), max(ydom[1], yt[-1])
    X = lambda x: ml + (x - x0) / (x1 - x0) * (w - ml - mr)
    Y = lambda y: mt + (1 - (y - y0) / (y1 - y0)) * (h - mt - mb)
    o = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart" aria-label="{esc(ylab)} by {esc(xlab)}">']
    for t in yt:
        o.append(f'<line class="grid" x1="{ml}" x2="{w - mr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>'
                 f'<text class="tick" x="{ml - 8}" y="{Y(t) + 4:.1f}" text-anchor="end">{tfmt(yfmt, t)}</text>')
    for t in (xticks or nice_ticks(x0, x1, 7)):
        if x0 <= t <= x1:
            o.append(f'<line class="axis" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{h - mb}" y2="{h - mb + 5}"/>'
                     f'<text class="tick" x="{X(t):.1f}" y="{h - mb + 19}" text-anchor="middle">{xfmt.format(t)}</text>')
    o.append(f'<line class="axis" x1="{ml}" x2="{w - mr}" y1="{h - mb}" y2="{h - mb}"/>')
    o.append(f'<text class="axlab" x="{(ml + w - mr) / 2:.0f}" y="{h - 6}" text-anchor="middle">{esc(xlab)}</text>')
    o.append(f'<text class="axlab" x="{ml - 44}" y="{mt - 2}" text-anchor="start" dy="-2">{esc(ylab)}</text>' if False else "")
    ends = []
    for s in series:
        segs, cur = [], []
        for x, y in s["pts"]:
            if pd.isna(y):
                if cur: segs.append(cur); cur = []
            else:
                cur.append((x, y))
        if cur: segs.append(cur)
        for seg in segs:
            d = " ".join(f"{'M' if i == 0 else 'L'}{X(x):.1f},{Y(y):.1f}" for i, (x, y) in enumerate(seg))
            o.append(f'<path class="ln {s["cls"]}{" dash" if s.get("dash") else ""}" d="{d}"/>')
            if markers or len(seg) == 1:
                for x, y in seg:
                    o.append(f'<circle class="mk {s["cls"]}" cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4"/>')
        for x, y in s["pts"]:
            if not pd.isna(y):
                tip = f'{s["name"]} · {tipx.format(x) if isinstance(tipx, str) else tipx(x)}: {yfmt.format(y)}'
                o.append(f'<circle class="hit" cx="{X(x):.1f}" cy="{Y(y):.1f}" r="9" data-tip="{esc(tip)}"/>')
        last = [p for p in s["pts"] if not pd.isna(p[1])]
        if label_ends and last:
            ends.append([Y(last[-1][1]), s])
    ends.sort(key=lambda e: e[0])
    for i in range(1, len(ends)):                     # keep end labels 15px apart
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 15)
    for yy, s in ends:
        o.append(f'<text class="endlab" x="{w - mr + 8}" y="{yy + 4:.1f}"><tspan class="sw {s["cls"]}">■</tspan> {esc(s["name"])}</text>')
    o.append("</svg>")
    return "".join(o)


def dot_chart(rows, series, xlab, xdom=None, xfmt="{:.2f}", w=720, rowh=30, lw=250):
    """Horizontal dot-and-whisker chart. rows: list of (label, {series_key: (value, se)}); series: [(key, name, cls)]."""
    mt, mb, mr = 10, 40, 24
    h = mt + mb + rowh * len(rows)
    vals = [v[0] - 1.96 * (v[1] or 0) for _, d in rows for v in d.values() if not pd.isna(v[0])]
    vals += [v[0] + 1.96 * (v[1] or 0) for _, d in rows for v in d.values() if not pd.isna(v[0])]
    x0, x1 = xdom or (min(0, min(vals)), max(vals) * 1.05)
    xt = nice_ticks(x0, x1, 6)
    x1 = max(x1, xt[-1])
    X = lambda x: lw + (x - x0) / (x1 - x0) * (w - lw - mr)
    o = [f'<svg viewBox="0 0 {w} {h}" role="img" class="chart" aria-label="{esc(xlab)}">']
    for t in xt:
        o.append(f'<line class="grid" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{mt}" y2="{h - mb}"/>'
                 f'<text class="tick" x="{X(t):.1f}" y="{h - mb + 18}" text-anchor="middle">{tfmt(xfmt, t)}</text>')
    o.append(f'<text class="axlab" x="{(lw + w - mr) / 2:.0f}" y="{h - 6}" text-anchor="middle">{esc(xlab)}</text>')
    k = len(series)
    for i, (lab, d) in enumerate(rows):
        yc = mt + rowh * (i + 0.5)
        o.append(f'<text class="rowlab" x="{lw - 12}" y="{yc + 4:.1f}" text-anchor="end">{esc(lab)}</text>')
        if i:
            o.append(f'<line class="rowrule" x1="{lw - 240}" x2="{w - mr}" y1="{mt + rowh * i:.1f}" y2="{mt + rowh * i:.1f}"/>')
        for j, (key, name, cls) in enumerate(series):
            if key not in d or pd.isna(d[key][0]):
                continue
            v, se = d[key]
            y = yc + (j - (k - 1) / 2) * 8
            if se and not pd.isna(se):
                o.append(f'<line class="whisk {cls}" x1="{X(v - 1.96 * se):.1f}" x2="{X(v + 1.96 * se):.1f}" y1="{y:.1f}" y2="{y:.1f}"/>')
            o.append(f'<circle class="mk {cls}" cx="{X(v):.1f}" cy="{y:.1f}" r="5"/>')
            tip = f"{lab} · {name}: {xfmt.format(v)}" + (f" (SE {se:.3f})" if se and not pd.isna(se) else "")
            o.append(f'<circle class="hit" cx="{X(v):.1f}" cy="{y:.1f}" r="10" data-tip="{esc(tip)}"/>')
    o.append("</svg>")
    return "".join(o)


def legend(series):
    return '<div class="legend">' + "".join(
        f'<span><i class="sw {cls}{" dashsw" if dash else ""}"></i>{esc(name)}</span>' for name, cls, dash in series) + "</div>"


def table(df, cols, caption=None, num=None):
    num = num or {}
    o = ['<div class="tblwrap"><table>']
    if caption:
        o.append(f"<caption>{caption}</caption>")
    o.append("<thead><tr>" + "".join(f"<th>{esc(c)}</th>" for c in cols) + "</tr></thead><tbody>")
    for _, r in df.iterrows():
        o.append("<tr>" + "".join(
            f'<td class="{"l" if (i == 0 or isinstance(r[c], str)) else "n"}">{esc(num.get(c, str)(r[c]) if c in num else r[c])}</td>' for i, c in enumerate(cols)) + "</tr>")
    o.append("</tbody></table></div>")
    return "".join(o)


def figure(title, chart, note, data_df=None, data_cols=None, num=None, leg=None):
    FIG[0] += 1
    n = FIG[0]
    o = [f'<figure id="fig{n}"><figcaption><span class="fno">Figure {n}</span> {title}</figcaption>']
    if leg:
        o.append(leg)
    o.append(f'<div class="chartwrap">{chart}</div><p class="fnote">{note}</p>')
    if data_df is not None:
        o.append(f"<details><summary>Data for figure {n}</summary>{table(data_df, data_cols, num=num)}</details>")
    o.append("</figure>")
    return "".join(o)


def tab(title, df, cols, note="", num=None):
    TAB[0] += 1
    return (f'<div class="tblock"><p class="tcap"><span class="fno">Table {TAB[0]}</span> {title}</p>'
            f'{table(df, cols, num=num)}' + (f'<p class="fnote">{note}</p>' if note else "") + "</div>")


# ------------------------------------------------------------------ data
def load():
    D = dict(
        est=pd.read_csv(os.path.join(EXT, "psid_estimates.csv")),
        roll=pd.read_csv(os.path.join(EXT, "psid_rolling.csv")),
        cmp=pd.read_csv(os.path.join(EXT, "source_compare.csv")),
        sipp_lag=pd.read_csv(os.path.join(EXT, "sipp_var_by_lag.csv")),
        cps_d1=pd.read_csv(os.path.join(EXT, "cps_var_d1_by_year.csv")),
        psid_d1=pd.read_csv(os.path.join(EXT, "psid_var_d1_by_year.csv")),
        prof=pd.read_csv(os.path.join(ROOT, "dataset", "age_profiles.csv")),
        t1=pd.read_csv(os.path.join(CGM, "table1_fixed_effects.csv")),
        t2=pd.read_csv(os.path.join(CGM, "table2_age_polynomial.csv")),
        t3=pd.read_csv(os.path.join(CGM, "table3_variances.csv")),
        sens=pd.read_csv(os.path.join(CGM, "sensitivity_variances.csv")),
    )
    e = D["est"]
    D["main"] = e[(e["measure"] == "cgm") & (e["sample"] == "drop_lt2k")]
    return D


def get(M, period, cut, group, col):
    r = M[(M["period"] == period) & (M["cut"] == cut) & (M["group"] == group)]
    return r[col].iloc[0] if len(r) else np.nan


# ------------------------------------------------------------------ sections
def build():
    D = load()
    M, R = D["main"], D["roll"]
    B = []

    # ---- key figures
    kf = [
        ("Permanent shock variance, all years", f'{get(M, "full", "all", "all", "s2_perm"):.3f}',
         f'1970s {get(M, "p1", "all", "all", "s2_perm"):.3f}, since 2007 {get(M, "p4", "all", "all", "s2_perm"):.3f}'),
        ("Transitory shock variance, all years", f'{get(M, "full", "all", "all", "s2_trans"):.3f}',
         f'1970s {get(M, "p1", "all", "all", "s2_trans"):.3f}, since 2007 {get(M, "p4", "all", "all", "s2_trans"):.3f}'),
        ("Income growth, age 25 to 50", f'{np.exp(get(M, "p4", "all", "all", "d_25_50")):.2f}<small>×</small>',
         f'since 2007; {np.exp(get(M, "p1", "all", "all", "d_25_50")):.2f}× in 1969-1980'),
        ("Replacement rates used in the model", "0.87 / 0.78 / 0.68", "no high school / high school / college"),
    ]
    kfh = '<div class="keys">' + "".join(
        f'<div class="key"><p class="kl">{a}</p><p class="kv">{b}</p><p class="kn">{c}</p></div>' for a, b, c in kf) + "</div>"

    # ---- section 1 summary
    B.append(sec("summary", "Summary", f"""
<p>This report estimates how American household labor income moves over a working life, following Cocco, Gomes and Maenhout (2005; "CGM"). Income has three parts: a predictable age profile; permanent shocks, which shift income for good; and transitory shocks, which last one year. We re-estimate CGM's model on the Panel Study of Income Dynamics (PSID) from 1969 to 2022, split it by education, industry, income level and birth cohort, follow it over time, and check it against two Census surveys, SIPP and CPS ASEC. The parameters feed a life cycle model; they are in <code>dataset/</code>.</p>
<ul class="find">
<li><b>The replication holds.</b> On CGM's own years (1969-1991) the age profiles and shock variances match theirs closely once incomes under $2,000 (1992 dollars) are dropped (Table 1).</li>
<li><b>Permanent risk doubled after the 1970s and has stayed up.</b> The variance of permanent shocks went from 0.012 in 1969-1980 to 0.025 in 1981-1992 and has been about 0.02 since (Figure 1).</li>
<li><b>Transitory risk rose in the 1990s</b> from about 0.065 to 0.10, and eased to about 0.08 in the 2010s (Figure 2).</li>
<li><b>Income now rises faster to midlife and falls less after 50.</b> From 25 to 50 the profile rises {np.exp(get(M, "p1", "all", "all", "d_25_50")):.2f}× in 1969-1980 and {np.exp(get(M, "p4", "all", "all", "d_25_50")):.2f}× in 2007-2022 (Figure 3).</li>
<li><b>Less education means more transitory risk,</b> and that gap has widened: since 2007 the transitory variance is {get(M, "p4", "education", "no_high_school", "s2_trans"):.3f} without a high school diploma and {get(M, "p4", "education", "college", "s2_trans"):.3f} with a degree. Permanent risk is now similar across groups.</li>
<li><b>Low earners face the largest transitory shocks and the flattest profiles;</b> industry matters for transitory risk more than for permanent risk.</li>
<li><b>SIPP and CPS agree on the direction of every trend,</b> but their panels are too short to split shocks into permanent and transitory, so the variances come from the PSID.</li>
</ul>"""))

    # ---- section 2 model & method
    B.append(sec("method", "The model and how it is estimated", f"""
<div class="eq">log Y<sub>it</sub> = f(t, Z<sub>it</sub>) + v<sub>it</sub> + ε<sub>it</sub>,&emsp; v<sub>it</sub> = v<sub>i,t−1</sub> + u<sub>it</sub>,&emsp; Var(u) = σ²<sub>u</sub>,&emsp; Var(ε) = σ²<sub>ε</sub></div>
<p><b>Income</b> is CGM's household measure: the head's and spouse's labor income plus unemployment and workers' compensation, Social Security, SSI, other welfare, child support and help from relatives, in 1992 dollars (CPI-U). <b>Sample</b>: the PSID's original SRC sample, male heads aged 20 to 65 (22 to 65 with a college degree), excluding the retired, housewives and students. Following the project decision of 10 October 2026, years with income under $2,000 (1992 dollars) are dropped; the full sample is the robustness check.</p>
<p><b>Age profile.</b> A fixed-effects regression of log income on age dummies, marital status and household size, estimated separately for each group; a cubic in age is fitted to the age dummies. Because the regression has no year effects, the profile includes the average real income growth of the years it covers, as in CGM. <b>Shocks.</b> With r<sub>d</sub> the change in residual log income over d years, Var(r<sub>d</sub>) = d·σ²<sub>u</sub> + 2σ²<sub>ε</sub> (Carroll and Samwick 1997). The two variances are the slope and half the intercept of a regression of Var(r<sub>d</sub>) on d. Lags are calendar years, so the PSID's two-year waves after 1997 contribute even lags; long periods use lags up to 22 years, shorter ones up to 11. Standard errors come from a bootstrap over people. <b>Replacement rate</b>: mean income including pensions of retired heads aged 65-75, over the group's fitted income at 65.</p>
<p><b>Groups.</b> Education: no high school diploma, high school (including some college), college degree. Industry: seven sectors from Census industry codes, the person's most common sector. Income: quintiles of a person's average income relative to others of the same age and year ("lifetime rank"), or of his first three years only ("initial rank"; variances then use later years only). Cohort: birth decade.</p>"""))

    # ---- section 3 replication
    t3, t2, sens = D["t3"], D["t2"], D["sens"]
    s2k = sens[sens["case"] == "drop_real_income_below_2k"].set_index("group")
    rep = []
    for g, lab, _ in EDU:
        a, b = t3.set_index("group").loc[g], t2.set_index("group").loc[g]
        rep.append(dict(Group=lab, perm_cgm=a["cgm_s2_perm"], perm_ours=a["s2_perm"], perm_2k=s2k.loc[g, "s2_perm"],
                        tr_cgm=a["cgm_s2_trans"], tr_ours=a["s2_trans"], tr_2k=s2k.loc[g, "s2_trans"],
                        peak=f'{int(b["cgm_peak_age"])} / {int(b["peak_age_p3"])}',
                        repl=f'{b["cgm_repl"]:.2f} / {b["repl_prof65_pens"]:.2f}'))
    rep = pd.DataFrame(rep)
    rep.columns = ["Group", "σ²u CGM", "σ²u ours", "σ²u ours, >$2k", "σ²ε CGM", "σ²ε ours", "σ²ε ours, >$2k",
                   "Peak age CGM / ours", "Replacement CGM / ours"]
    num = {c: f3 for c in rep.columns[1:7]}
    B.append(sec("replication", "Replicating CGM", f"""
<p>On CGM's sample and years we get 1,139 / 2,919 / 1,134 households against their 1,104 / 2,816 / 1,110, nearly the same marital and household-size effects, and age profiles that match theirs up to the mid-40s. Our profiles for the two non-college groups fall more after 50. Our shock variances are higher on the full sample; the gap comes from a few very low incomes (under $2,000 is 0.3% of high-school observations but 16% of the residual variance). Without them the variances are close to CGM's.</p>
{tab("CGM (2005) against our replication, income years 1969-1991", rep, list(rep.columns), "σ²u permanent and σ²ε transitory shock variance. “ours” is the full sample, “>$2k” drops incomes under $2,000 in 1992 dollars. CGM's replacement rate cannot be reproduced from their stated income definition; ours includes pensions and divides by the age profile at 65 (cgm/README.md).", num)}"""))

    # ---- section 4 trends over time
    def roll_series(measure, col, groups):
        x = R[R["measure"] == measure].copy()
        x["mid"] = x["years"].str[:4].astype(int) + 5.5
        out = []
        for g, lab, cls in groups:
            s = x[x["group"] == g].sort_values("mid")
            out.append(dict(name=lab, cls=cls, pts=list(zip(s["mid"], s[col]))))
        return out, x

    grp_all = [("all", "All", "s0")] + EDU
    sp, x = roll_series("cgm", "s2_perm", grp_all)
    st, _ = roll_series("cgm", "s2_trans", grp_all)
    rd = x.pivot(index="years", columns="group", values=["s2_perm", "s2_trans"]).reset_index()
    rd.columns = ["Window"] + [f"{a} {EDU_LABEL.get(b, 'All')}".replace("s2_perm", "σ²u").replace("s2_trans", "σ²ε") for a, b in rd.columns[1:]]
    fig1 = figure("Permanent shock variance, rolling 12-year windows",
                  line_chart(sp, "Middle of the 12-year window", "σ²u", ydom=(0, 0.04), yfmt="{:.3f}", tipx=lambda m: f"{int(m - 5.5)}-{int(m + 5.5)}"),
                  "PSID, CGM household income, default sample. Each point is a separate estimate on the 12 income years around it (lags up to 11). Bootstrap standard errors are 0.002-0.003 for all households and 0.003-0.008 by education.",
                  rd, list(rd.columns), {c: f3 for c in rd.columns[1:]}, leg=legend([(s["name"], s["cls"], False) for s in sp]))
    fig2 = figure("Transitory shock variance, rolling 12-year windows",
                  line_chart(st, "Middle of the 12-year window", "σ²ε", ydom=(0, 0.17), yfmt="{:.2f}", tipx=lambda m: f"{int(m - 5.5)}-{int(m + 5.5)}"),
                  "PSID, CGM household income, default sample. The step in the early 1990s coincides with the PSID's move to computer-assisted interviews (1993) and a change in how some transfers were recorded (1994-2003); head earnings alone show the same rise.",
                  leg=legend([(s["name"], s["cls"], False) for s in st]))
    P = D["prof"]
    pser = []
    for p, lab, cls in PERIODS:
        s = P[(P["period"] == p) & (P["cut"] == "all")]
        base = s.loc[s["age"] == 25, "log_level"].iloc[0]
        pser.append(dict(name=lab, cls=cls, pts=[(a, np.exp(v - base)) for a, v in zip(s["age"], s["log_level"]) if a >= 25]))
    pt = pd.DataFrame({"Age": range(25, 66, 5)})
    for sdict in pser:
        d = dict(sdict["pts"])
        pt[sdict["name"]] = [d.get(a) for a in pt["Age"]]
    fig3 = figure("Age profile of income by period, relative to age 25",
                  line_chart(pser, "Age", "Income relative to age 25", yfmt="{:.1f}", tipx="age {:.0f}"),
                  "PSID, all education groups, fitted cubic, at mean marital status and household size; 1.0 = income at 25. Profiles include each period's aggregate income growth, so they carry its business cycle too.",
                  pt, list(pt.columns), {c: f2 for c in pt.columns[1:]}, leg=legend([(s["name"], s["cls"], False) for s in pser]))
    ttab = []
    for p, lab in [("p1", "1969-1980"), ("p2", "1981-1992"), ("p3", "1993-2006"), ("p4", "2007-2022"), ("full", "All, 1969-2022")]:
        ttab.append({"Income years": lab, "σ²u": get(M, p, "all", "all", "s2_perm"), "SE ": get(M, p, "all", "all", "s2_perm_se"),
                     "σ²ε": get(M, p, "all", "all", "s2_trans"), "SE": get(M, p, "all", "all", "s2_trans_se"),
                     "Growth 25→50": np.exp(get(M, p, "all", "all", "d_25_50")), "Change 50→60": np.exp(get(M, p, "all", "all", "d_50_60")),
                     "Peak age": get(M, p, "all", "all", "peak_age"), "Replacement rate": get(M, p, "all", "all", "repl_prof65_pens")})
    ttab = pd.DataFrame(ttab)
    B.append(sec("trends", "How the income process has changed", f"""
<p>Permanent risk roughly doubled between the 1970s and the 1980s and has not come back down. Transitory risk rose later, through the 1990s, and has eased somewhat since 2008. The age profile has become steeper: income now grows more between 25 and 50 and falls less in the 50s.</p>
{fig1}{fig2}{fig3}
{tab("The income process by period, all households", ttab, list(ttab.columns), "Growth and change are ratios of fitted income (e.g. 2.00 = doubles). Replacement rates by period rest on a 12-16 year profile and are noisy; use the all-years value.", {c: (f3 if c.startswith(("σ", "SE")) else f2) for c in ttab.columns[1:]} | {"Peak age": lambda v: f"{v:.0f}"})}"""))

    # ---- section 5 education
    eser = []
    for g, lab, cls in EDU:
        s = P[(P["period"] == "full") & (P["cut"] == "education") & (P["group"] == g)]
        eser.append(dict(name=lab, cls=cls, pts=list(zip(s["age"], s["level_k2024"]))))
    et = pd.DataFrame({"Age": range(25, 66, 5)})
    for sd in eser:
        d = dict(sd["pts"]); et[sd["name"]] = [d.get(a) for a in et["Age"]]
    fig4 = figure("Fitted household income by age and education, 1969-2022",
                  line_chart(eser, "Age", "Thousands of 2024 dollars", yfmt="{:.0f}", tipx="age {:.0f}"),
                  "PSID, CGM household income, cubic profile at mean marital status and household size, converted from 1992 to 2024 dollars with the CPI-U.",
                  et, list(et.columns), {c: (lambda v: f"{v:.1f}") for c in et.columns[1:]}, leg=legend([(s["name"], s["cls"], False) for s in eser]))
    erows = []
    for p, lab, _ in PERIODS + [("full", "All, 1969-2022", "")]:
        erows.append((lab, {g: (get(M, p, "education", g, "s2_trans"), get(M, p, "education", g, "s2_trans_se")) for g, _, _ in EDU}))
    prow = [(lab, {g: (get(M, p, "education", g, "s2_perm"), get(M, p, "education", g, "s2_perm_se")) for g, _, _ in EDU})
            for p, lab, _ in PERIODS + [("full", "All, 1969-2022", "")]]
    eser_k = [(g, lab, cls) for g, lab, cls in EDU]
    fig5 = figure("Shock variances by education and period",
                  '<div class="pair"><div><p class="sub">Permanent, σ²u</p>' + dot_chart(prow, eser_k, "σ²u", xdom=(0, 0.04), xfmt="{:.2f}", w=430, lw=118) +
                  '</div><div><p class="sub">Transitory, σ²ε</p>' + dot_chart(erows, eser_k, "σ²ε", xdom=(0, 0.2), xfmt="{:.2f}", w=430, lw=118) + "</div></div>",
                  "Dots are estimates, lines 95% bootstrap intervals. PSID, CGM household income, default sample.",
                  leg=legend([(lab, cls, False) for _, lab, cls in EDU]))
    edt = []
    for p, lab in [("cgm", "CGM years, 1969-1991"), ("full", "All, 1969-2022"), ("p4", "2007-2022")]:
        for g, gl, _ in EDU:
            edt.append({"Period": lab, "Education": gl, "σ²u": get(M, p, "education", g, "s2_perm"), "σ²ε": get(M, p, "education", g, "s2_trans"),
                        "Peak age": get(M, p, "education", g, "peak_age"), "Growth 25→50": np.exp(get(M, p, "education", g, "d_25_50")),
                        "Replacement rate": get(M, p, "education", g, "repl_prof65_pens")})
    edt = pd.DataFrame(edt)
    B.append(sec("education", "By education", f"""
<p>College graduates start lower, rise far faster and peak later (around 47); households without a high school diploma peak in their early 40s. Transitory risk falls with education, and since the 1990s the gap has widened: the no-diploma group's transitory variance has roughly doubled while the college group's is back near its 1970s level. Permanent risk was highest for college graduates in CGM's years and is now about the same for all three groups.</p>
{fig4}{fig5}
{tab("Education groups: shocks, profile and replacement rate", edt, list(edt.columns), "Default sample. The replacement rates used in the model stay at 0.87 / 0.78 / 0.68 (CGM years, full sample, with pensions), the project's choice of 11 October 2026.", {"σ²u": f3, "σ²ε": f3, "Peak age": lambda v: f"{v:.0f}", "Growth 25→50": f2, "Replacement rate": f2})}"""))

    # ---- section 6 industry
    ind = M[(M["period"] == "full") & (M["cut"] == "industry")].sort_values("s2_trans")
    irows_t = [(SECTOR_LABEL[g], {"t": (t, se)}) for g, t, se in zip(ind["group"], ind["s2_trans"], ind["s2_trans_se"])]
    irows_p = [(SECTOR_LABEL[g], {"p": (t, se)}) for g, t, se in zip(ind["group"], ind["s2_perm"], ind["s2_perm_se"])]
    fig6 = figure("Shock variances by industry, 1969-2022",
                  '<div class="pair"><div><p class="sub">Transitory, σ²ε</p>' + dot_chart(irows_t, [("t", "σ²ε", "s1")], "σ²ε", xdom=(0, 0.17), w=470, lw=222) +
                  '</div><div><p class="sub">Permanent, σ²u</p>' + dot_chart(irows_p, [("p", "σ²u", "s1")], "σ²u", xdom=(0, 0.025), xfmt="{:.3f}", w=470, lw=222) + "</div></div>",
                  "Sector is the person's most common one over his years in the sample. Dots are estimates, lines 95% bootstrap intervals. PSID, CGM household income.")
    it = ind.assign(Sector=ind["group"].map(SECTOR_LABEL), **{"Growth 25→50": np.exp(ind["d_25_50"])})[
        ["Sector", "n_units", "s2_perm", "s2_trans", "peak_age", "Growth 25→50", "repl_prof65_pens"]]
    it.columns = ["Sector", "Households", "σ²u", "σ²ε", "Peak age", "Growth 25→50", "Replacement rate"]
    B.append(sec("industry", "By industry", f"""
<p>Industry sorts households mainly by transitory risk. Public administration and manufacturing have the smallest year-to-year swings; agriculture, mining and construction have more than twice as much. Permanent risk varies less, with finance and business services the highest. Public administration's replacement rate above 1 reflects government pensions.</p>
{fig6}
{tab("Industry: shocks, profile and replacement rate, 1969-2022", it, list(it.columns), "Industry codes change system in 2003; legal, engineering and accounting services move from the services sector to finance and business services at that point.", {"Households": lambda v: f"{v:,.0f}", "σ²u": f3, "σ²ε": f3, "Peak age": lambda v: f"{v:.0f}", "Growth 25→50": f2, "Replacement rate": f2})}"""))

    # ---- section 7 income quintiles
    q = M[(M["period"] == "full") & (M["cut"] == "income_q")].set_index("group")
    qi = M[(M["period"] == "full") & (M["cut"] == "income_q_init")].set_index("group")
    qs = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    qrow = [(f"{g}{' (lowest)' if g == 'Q1' else ' (highest)' if g == 'Q5' else ''}",
             {"life": (q.loc[g, "s2_trans"], q.loc[g, "s2_trans_se"]), "init": (qi.loc[g, "s2_trans"], qi.loc[g, "s2_trans_se"])}) for g in qs]
    qser = [("life", "Lifetime rank", "s1"), ("init", "Initial rank", "s2")]
    fig7 = figure("Transitory shock variance by income quintile, 1969-2022",
                  dot_chart(qrow, qser, "σ²ε", xdom=(0, 0.22), w=720, lw=140),
                  "Lifetime rank: quintile of a person's average income relative to others of his age and year. Initial rank: quintile from his first three years, with the variance estimated on later years only, so the ranking years carry no shocks. 95% bootstrap intervals.",
                  leg=legend([(n, c, False) for _, n, c in qser]))
    qp = []
    for g, cls in zip(qs, ["o1", "o2", "o3", "o4", "o5"]):
        s = P[(P["period"] == "full") & (P["cut"] == "income_q") & (P["group"] == g)]
        qp.append(dict(name=g, cls=cls, pts=list(zip(s["age"], s["level_k2024"]))))
    fig8 = figure("Fitted household income by age and income quintile, 1969-2022",
                  line_chart(qp, "Age", "Thousands of 2024 dollars", yfmt="{:.0f}", tipx="age {:.0f}"),
                  "Lifetime-rank quintiles. Cubic profile at mean marital status and household size, CPI-U to 2024 dollars.",
                  leg=legend([(s["name"], s["cls"], False) for s in qp]))
    qt = pd.DataFrame({"Quintile": qs, "σ²u lifetime": q.loc[qs, "s2_perm"].values, "σ²ε lifetime": q.loc[qs, "s2_trans"].values,
                       "σ²u initial": qi.loc[qs, "s2_perm"].values, "σ²ε initial": qi.loc[qs, "s2_trans"].values,
                       "Peak age": q.loc[qs, "peak_age"].values, "Replacement rate": q.loc[qs, "repl_prof65_pens"].values})
    B.append(sec("income", "By income level", f"""
<p>Low earners face much larger transitory shocks: the transitory variance falls from {q.loc['Q1', 's2_trans']:.2f} in the bottom quintile to about {q.loc['Q4', 's2_trans']:.2f} at the top. Part of that is mechanical, since a bad year also lowers a person's lifetime rank; ranking on the first three years removes that link and roughly halves the gap ({qi.loc['Q1', 's2_trans']:.3f} against {qi.loc['Q5', 's2_trans']:.3f}). Permanent risk is about the same in every quintile under that ranking. Profiles differ more by income than by any other cut: the bottom quintile peaks in its mid-30s, the top keeps rising into its 50s, and Social Security replaces a larger share of low incomes.</p>
{fig7}{fig8}
{tab("Income quintiles, 1969-2022", qt, list(qt.columns), "", {c: f3 for c in qt.columns[1:5]} | {"Peak age": lambda v: f"{v:.0f}", "Replacement rate": f2})}"""))

    # ---- section 8 cohorts
    co = M[(M["period"] == "full") & (M["cut"] == "cohort") & M["group"].isin(["1930s", "1940s", "1950s", "1960s", "1970s"])]
    crow_t = [(f"Born {g}", {"t": (t, se)}) for g, t, se in zip(co["group"], co["s2_trans"], co["s2_trans_se"])]
    crow_p = [(f"Born {g}", {"p": (t, se)}) for g, t, se in zip(co["group"], co["s2_perm"], co["s2_perm_se"])]
    fig9 = figure("Shock variances by birth decade",
                  '<div class="pair"><div><p class="sub">Transitory, σ²ε</p>' + dot_chart(crow_t, [("t", "σ²ε", "s1")], "σ²ε", xdom=(0, 0.17), w=430, lw=118) +
                  '</div><div><p class="sub">Permanent, σ²u</p>' + dot_chart(crow_p, [("p", "σ²u", "s1")], "σ²u", xdom=(0, 0.025), xfmt="{:.3f}", w=430, lw=118) + "</div></div>",
                  "PSID, all years. Each cohort is seen only over the ages it reached between 1969 and 2022: those born in the 1930s mainly after 35, those born in the 1970s mainly before 50. Earlier and later cohorts are too thin to show. 95% bootstrap intervals.")
    B.append(sec("cohorts", "By birth cohort", f"""
<p>Each later cohort has faced larger transitory shocks, from about 0.08 for men born in the 1930s to 0.14 for those born in the 1970s, while permanent risk is 0.013-0.016 for every cohort. Because a cohort is observed only over part of its working life, this cut mixes cohort and period; the period estimates above are the cleaner view of change over time.</p>
{fig9}"""))

    # ---- section 9 sources
    C = D["cmp"]
    ps = D["psid_d1"]; ps = ps[(ps["measure"] == "head_earn") & (ps["group"] == "all")]
    cd = D["cps_d1"]; cd = cd[cd["group"] == "all"]
    sl = D["sipp_lag"]; sl = sl[(sl["d"] == 1) & (sl["cut"] == "all") & sl["period"].str.startswith("panel")]
    sl = sl.assign(mid=sl["years"].str[:4].astype(int) + (sl["years"].str[5:].astype(int) - sl["years"].str[:4].astype(int) - 1) / 2)
    old = sl[sl["mid"] < 2013].sort_values("mid"); new = sl[sl["mid"] >= 2013].sort_values("mid")
    def gaps(xs, ys):                                  # break annual lines where years are missing
        out = []
        for x, y in zip(xs, ys):
            if out and x - out[-1][0] > 1:
                out.append((x - 1, np.nan))
            out.append((x, y))
        return out
    vser = [dict(name="PSID", cls="s1", pts=gaps(ps["income_year_start"], ps["var_d1"])),
            dict(name="CPS ASEC", cls="s2", pts=gaps(cd["income_year"], cd["var_d1"])),
            dict(name="SIPP 1996-2008 panels", cls="s3", pts=list(zip(old["mid"], old["var"]))),
            dict(name="SIPP 2014+ panels", cls="s3", dash=True, pts=list(zip(new["mid"], new["var"])))]
    fig10 = figure("Variance of one-year changes in men's log earnings, three surveys",
                   line_chart(vser, "Year of the first of the two years", "Var(Δ log earnings)", ydom=(0, 0.4), yfmt="{:.2f}", markers=True),
                   "Men aged 20-65 with earnings of at least $2,000 (1992 dollars), own earnings. PSID: residual change, annual waves only (to 1996); its jump in 1991-92 coincides with the move to computer-assisted interviews in the 1993 survey. CPS: matched March pairs (ASEC 1988-1992 and 1996-2014), demeaned by year and age. SIPP: each panel's pooled one-year changes, plotted at the panel's middle year; the 2014 redesign raised the level by about 70% (dashed).",
                   leg=legend([(s["name"], s["cls"], s.get("dash", False)) for s in vser]))
    srcrows = []
    lab = {("psid", "p2"): "PSID 1981-1992", ("psid", "p3"): "PSID 1993-2006", ("psid", "p4"): "PSID 2007-2022",
           ("sipp", "era_old_1995_2013"): "SIPP 1996-2012", ("sipp", "era_new_2013_2024"): "SIPP 2013-2024",
           ("cps", "p3"): "CPS 1993-2006", ("cps", "p4"): "CPS 2007-2025"}
    for (src, per), name in lab.items():
        r = C[(C["source"] == src) & (C["period"] == per) & (C["group"] == "all")].iloc[0]
        srcrows.append({"Source, years": name, "Growth 25→50": np.exp(r["d_25_50"]), "Change 50→60": np.exp(r["d_50_60"]),
                        "Var 1-yr change": r["var_d1"], "σ²u": r["s2_perm"], "σ²ε": r["s2_trans"],
                        "σ²u lags 1-4": r["s2_perm_short"]})
    srct = pd.DataFrame(srcrows)
    B.append(sec("sources", "Checking against SIPP and CPS ASEC", f"""
<p>SIPP and CPS measure each person's own earnings, so the comparison uses men's own earnings in all three surveys (for the PSID, the head's labor income). All three show the same changes: income rising faster to midlife, a smaller decline after 50, and larger year-to-year swings over time. Levels differ for known reasons. The CPS follows addresses, not people, and its one-year changes include matching and reporting error. SIPP's 2014 redesign raised measured volatility by about 70%, so its two designs are never pooled.</p>
<p>The split between permanent and transitory risk needs long panels. SIPP follows people for 2 to 4 years, and with only those short lags the PSID itself gives a permanent variance 1.3 to 2.2 times its long-lag estimate. The CPS method (the rise in earnings inequality with age within a cohort) gives lower values. We therefore take the shock variances from the PSID and use SIPP and CPS as checks on the profile and on volatility.</p>
{fig10}
{tab("Men's own earnings in three surveys", srct, list(srct.columns), "Growth and change are ratios of fitted earnings. PSID and SIPP σ²u, σ²ε: Carroll-Samwick (PSID lags up to 11, SIPP up to 4). CPS σ²u: within-cohort variance growth with age (Deaton-Paxson), σ²ε from the variance of matched one-year changes. “lags 1-4” refits PSID with only the lags a SIPP panel allows.", {c: (f2 if c.startswith(("Growth", "Change")) else f3) for c in srct.columns[1:]})}"""))

    # ---- section 10 parameters
    pr = []
    for p, plab in [("full", "Baseline, 1969-2022"), ("p4", "Recent, 2007-2022")]:
        for g, gl, _ in EDU:
            r = M[(M["period"] == p) & (M["cut"] == "education") & (M["group"] == g)].iloc[0]
            pr.append({"Set": plab, "Education": gl, "const": r["const"], "c0": r["p3_c0"], "c1": r["p3_c1"], "c2": r["p3_c2"], "c3": r["p3_c3"],
                       "married": r["married"], "hhcomp": r["hhcomp"], "σ²u": r["s2_perm"], "σ²ε": r["s2_trans"],
                       "λ": {"no_high_school": 0.87, "high_school": 0.78, "college": 0.68}[g]})
    pr = pd.DataFrame(pr)
    B.append(sec("parameters", "Parameters for the life cycle model", f"""
<p>The recommended baseline is the PSID estimate by education over all years, 1969-2022, with the replacement rates chosen for the project. For a model of today's workers, the 2007-2022 set has a steeper profile and, for the less educated, larger transitory shocks. Every other cut and period is in the dataset.</p>
<div class="eq small">log Y = const + married·m + hhcomp·h + c0 + c1·age + c2·age²/10 + c3·age³/100 + v + ε<br>retirement income = λ · exp(const + married·m̄ + hhcomp·h̄ + f(65))</div>
{tab("Recommended parameter sets (income in thousands of 1992 dollars)", pr, list(pr.columns), "m = 1 with a spouse present; h = family members besides head and spouse. λ: replacement rate. Sample means of m and h, standard errors and fitted income by age are in the dataset.", {c: (lambda v: f"{v:.4f}") for c in ["const", "c0", "c1", "c2", "c3", "married", "hhcomp", "σ²u", "σ²ε"]} | {"λ": f2})}
<table class="files"><tbody>
<tr><td><code>dataset/income_process_model.json</code></td><td>The baseline, recent and CGM-years sets by education, ready for a model to read.</td></tr>
<tr><td><code>dataset/income_process_parameters.csv</code></td><td>Every parameter for every cut (all, education, industry, income quintile, cohort) and period, with standard errors and units.</td></tr>
<tr><td><code>dataset/age_profiles.csv</code></td><td>Fitted income at each age 20-65 for every cut and period, in log points and thousands of 1992 and 2024 dollars.</td></tr>
<tr><td><code>extend/output/</code></td><td>All estimates, including the full sample, the head-earnings measure, SIPP and CPS, rolling windows and the variance at each lag.</td></tr>
</tbody></table>"""))

    # ---- section 11 caveats & sources
    B.append(sec("caveats", "Data notes and caveats", """
<ul>
<li><b>Sample.</b> Male heads in the PSID's original SRC sample, unweighted, as in CGM. The low-income SEO sample and the immigrant refreshers are excluded.</li>
<li><b>PSID changes.</b> Computer-assisted interviews from 1993, a new labor-income definition in 1994 (we restore business and farm labor income), transfers recorded as amounts per period in 1994-2003 (we annualize them), two-year waves from 1997, and clusters of imputed incomes in 1997 and 1999.</li>
<li><b>Profiles include the cycle.</b> Like CGM's, the profiles have no year effects, so each one carries the real growth and recessions of its window. Compare shapes, not single peaks.</li>
<li><b>Lag range.</b> The permanent-shock estimate depends on how many years apart the compared incomes are; the long periods use up to 22 years, the others up to 11.</li>
<li><b>Grouping.</b> Industry is a person's most common sector; people who switch count in one only. Industry codes change system in 2003. Use the initial income rank for income-group variances.</li>
<li><b>Replacement rates.</b> CGM's published rates (0.89 / 0.68 / 0.94) cannot be reproduced from their stated income definition; ours include pensions and are measured against the profile at 65.</li>
</ul>""") + sec("sources-list", "Sources", """
<ol class="refs">
<li>Cocco, J. F., F. J. Gomes and P. J. Maenhout (2005). Consumption and portfolio choice over the life cycle. <i>Review of Financial Studies</i> 18(2): 491-533.</li>
<li>Panel Study of Income Dynamics, public use data, 1968-2023 family and individual files. Survey Research Center, Institute for Social Research, University of Michigan. Extracts J366052, J366057, J366062, J366067 (October 2026).</li>
<li>U.S. Census Bureau. Survey of Income and Program Participation, 1996, 2001, 2004, 2008 and 2014 panels and SIPP 2018-2025 public-use files.</li>
<li>U.S. Census Bureau. Current Population Survey, Annual Social and Economic Supplement, 1988-2026 public-use files (1988-1997 via NBER).</li>
<li>Bureau of Labor Statistics. Consumer Price Index for All Urban Consumers (CPI-U), annual average.</li>
<li>Carroll, C. D. and A. A. Samwick (1997). The nature of precautionary wealth. <i>Journal of Monetary Economics</i> 40(1): 41-71.</li>
<li>Deaton, A. and C. Paxson (1994). Intertemporal choice and inequality. <i>Journal of Political Economy</i> 102(3): 437-467.</li>
<li>Madrian, B. C. and L. J. Lefgren (2000). An approach to longitudinally matching Current Population Survey respondents. <i>Journal of Economic and Social Measurement</i> 26(1): 31-62.</li>
</ol>
<p class="meta">Code and data: github.com/richyuen/income-trends (<code>cgm/</code>, <code>extend/</code>, <code>dataset/</code>, <code>report/</code>). Built from the repository outputs by <code>report/build.py</code>.</p>"""))
    return kfh, B


def sec(id_, title, body):
    return f'<section id="{id_}"><h2>{esc(title)}</h2>{body}</section>'


CSS = """
/* Layout: a single reading column (about 68ch) with charts allowed a little wider; a slim contents list under the
   masthead. The look borrows from a statistical working paper: numbered figures, source notes under each, ledger rules. */
:root{
  --bg:#f7f8f6; --surface:#ffffff; --ink:#15191d; --ink-2:#465058; --muted:#6c767e; --rule:#d8ddd9; --rule-strong:#15191d;
  --accent:#1d6b57; --link:#1d5a8c; --grid:#e7ebe8; --axis:#a9b2ad; --band:#eef1ef;
  --s0:#15191d; --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a;
  --o1:#86b6ef; --o2:#5598e7; --o3:#256abf; --o4:#104281; --o5:#0d366b;
  --tip-bg:#15191d; --tip-fg:#ffffff;
  --display:"Fraunces",Georgia,"Times New Roman",serif;
  --body:"Source Sans 3","Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){color-scheme:dark;
  --bg:#101312; --surface:#171b1a; --ink:#eef1ef; --ink-2:#c1c9c5; --muted:#8f9994; --rule:#2c3330; --rule-strong:#eef1ef;
  --accent:#6fd0b2; --link:#8ab4f8; --grid:#252b29; --axis:#4a534f; --band:#1d2220;
  --s0:#eef1ef; --s1:#3987e5; --s2:#d95926; --s3:#199e70;
  --o1:#184f95; --o2:#2a78d6; --o3:#5598e7; --o4:#86b6ef; --o5:#b7d3f6; --tip-bg:#eef1ef; --tip-fg:#15191d;}}
:root[data-theme="dark"]{color-scheme:dark;
  --bg:#101312; --surface:#171b1a; --ink:#eef1ef; --ink-2:#c1c9c5; --muted:#8f9994; --rule:#2c3330; --rule-strong:#eef1ef;
  --accent:#6fd0b2; --link:#8ab4f8; --grid:#252b29; --axis:#4a534f; --band:#1d2220;
  --s0:#eef1ef; --s1:#3987e5; --s2:#d95926; --s3:#199e70;
  --o1:#184f95; --o2:#2a78d6; --o3:#5598e7; --o4:#86b6ef; --o5:#b7d3f6; --tip-bg:#eef1ef; --tip-fg:#15191d;}
*,*::before,*::after{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:400 1.0625rem/1.6 var(--body);-webkit-font-smoothing:antialiased}
a{color:var(--link)}
:focus-visible{outline:2px solid var(--link);outline-offset:2px}
.wrap{max-width:960px;margin-inline:auto;padding-inline:clamp(16px,4vw,40px);padding-block:clamp(24px,5vw,56px) 80px}
.eyebrow{font:500 .74rem/1.3 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--accent);margin:0 0 .8rem}
h1{font:600 clamp(2.1rem,5.4vw,3.4rem)/1.05 var(--display);letter-spacing:-.015em;margin:0;max-width:18ch;text-wrap:balance}
.deck{font-size:clamp(1.05rem,1.8vw,1.22rem);color:var(--ink-2);max-width:60ch;margin:1rem 0 0}
.meta{font:400 .82rem/1.5 var(--body);color:var(--muted);margin:.9rem 0 0}
.keys{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:2px solid var(--rule-strong);border-bottom:1px solid var(--rule);margin:2rem 0 0}
.key{padding:.8rem 1rem 1rem 0;min-width:0}
.key+.key{padding-left:1rem;border-left:1px solid var(--rule)}
.kl{font:600 .78rem/1.3 var(--body);color:var(--ink-2);margin:0;min-height:2.6em}
.kv{font:600 clamp(1.5rem,3vw,2rem)/1.1 var(--display);margin:.35rem 0 0;font-variant-numeric:tabular-nums}
.kv small{font-size:.6em;margin-left:.08em}
.kn{font:400 .8rem/1.4 var(--body);color:var(--muted);margin:.35rem 0 0}
@media (max-width:760px){.keys{grid-template-columns:repeat(2,minmax(0,1fr))}.key:nth-child(3){padding-left:0;border-left:0}.key:nth-child(n+3){border-top:1px solid var(--rule)}}
@media (max-width:420px){.keys{grid-template-columns:minmax(0,1fr)}.key{padding-left:0!important;border-left:0!important}.key+.key{border-top:1px solid var(--rule)}.kl{min-height:0}}
nav.toc{margin:2rem 0 0;font:400 .9rem/1.4 var(--body)}
nav.toc ol{margin:0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:.35rem 1.2rem;counter-reset:t}
nav.toc li{counter-increment:t}
nav.toc a{color:var(--ink-2);text-decoration:none}
nav.toc a::before{content:counter(t);font:500 .72rem var(--mono);color:var(--accent);margin-right:.4em}
nav.toc a:hover{color:var(--ink);text-decoration:underline}
section{margin-top:3.2rem;counter-increment:s}
main{counter-reset:s}
h2{font:600 clamp(1.45rem,3vw,1.85rem)/1.2 var(--display);margin:0 0 .9rem;padding-top:.9rem;border-top:1px solid var(--rule-strong);text-wrap:balance}
h2::before{content:counter(s);font:500 .8rem var(--mono);color:var(--accent);display:block;margin-bottom:.35rem;letter-spacing:.06em}
section p,section li{max-width:68ch}
ul.find{padding-left:1.1rem}
ul.find li{margin:.45rem 0}
code{font:400 .86em var(--mono);background:var(--band);padding:.05em .3em;border-radius:3px}
.eq{font:400 1rem/1.7 var(--mono);background:var(--surface);border:1px solid var(--rule);padding:.9rem 1rem;margin:1.2rem 0;overflow-x:auto;max-width:100%}
.eq.small{font-size:.9rem}
figure{margin:2rem 0;padding:1rem 0 0;border-top:1px solid var(--rule)}
figcaption,.tcap{font:600 1rem/1.35 var(--body);margin:0 0 .5rem;text-wrap:balance}
.fno{font:500 .74rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin-right:.5em}
.chartwrap{overflow-x:auto;background:var(--surface);border:1px solid var(--rule);padding:12px 8px 4px}
.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media (max-width:720px){.pair{grid-template-columns:minmax(0,1fr)}}
.pair>div{min-width:0}
.sub{font:600 .82rem/1.3 var(--body);color:var(--ink-2);margin:0 0 .2rem 4px}
svg.chart{display:block;width:100%;height:auto;min-width:420px;font-family:var(--body)}
.grid{stroke:var(--grid);stroke-width:1}
.axis{stroke:var(--axis);stroke-width:1}
.rowrule{stroke:var(--grid);stroke-width:1}
.tick{fill:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
.axlab{fill:var(--ink-2);font-size:12.5px}
.rowlab{fill:var(--ink);font-size:13px}
.endlab{fill:var(--ink);font-size:12.5px}
.ln{fill:none;stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round}
.ln.dash{stroke-dasharray:6 4}
.whisk{stroke-width:2;stroke-linecap:round;opacity:.55}
.mk{stroke:var(--surface);stroke-width:2}
.hit{fill:transparent;stroke:none;cursor:default}
.hit:hover+.hit{}
.s0{stroke:var(--s0);fill:var(--s0);color:var(--s0)} .s1{stroke:var(--s1);fill:var(--s1);color:var(--s1)}
.s2{stroke:var(--s2);fill:var(--s2);color:var(--s2)} .s3{stroke:var(--s3);fill:var(--s3);color:var(--s3)}
.o1{stroke:var(--o1);fill:var(--o1);color:var(--o1)} .o2{stroke:var(--o2);fill:var(--o2);color:var(--o2)}
.o3{stroke:var(--o3);fill:var(--o3);color:var(--o3)} .o4{stroke:var(--o4);fill:var(--o4);color:var(--o4)}
.o5{stroke:var(--o5);fill:var(--o5);color:var(--o5)}
.ln.s0,.ln.s1,.ln.s2,.ln.s3,.ln.o1,.ln.o2,.ln.o3,.ln.o4,.ln.o5,.whisk{fill:none}
tspan.sw{stroke:none}
.legend{display:flex;flex-wrap:wrap;gap:.3rem 1.1rem;font:400 .86rem/1.3 var(--body);color:var(--ink-2);margin:0 0 .5rem}
.legend span{display:inline-flex;align-items:center;gap:.4em}
.legend i.sw{display:inline-block;width:18px;height:3px;border-radius:2px;background:currentColor}
.legend i.dashsw{background:repeating-linear-gradient(90deg,currentColor 0 6px,transparent 6px 9px)}
.fnote{font:400 .84rem/1.5 var(--body);color:var(--muted);margin:.55rem 0 0;max-width:80ch}
details{margin-top:.5rem;font-size:.88rem}
summary{cursor:pointer;color:var(--link);font-weight:600}
.tblock{margin:2rem 0}
.tblwrap{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;font:400 .88rem/1.35 var(--body);font-variant-numeric:tabular-nums;width:100%;background:var(--surface)}
caption{text-align:left}
th{font-weight:600;text-align:right;padding:.45rem .6rem;border-bottom:1.5px solid var(--rule-strong);vertical-align:bottom;white-space:nowrap}
th:first-child{text-align:left}
td{padding:.38rem .6rem;border-bottom:1px solid var(--rule)}
td.n{text-align:right;white-space:nowrap}
td.l{text-align:left}
table.files{margin-top:1.4rem}
table.files td{vertical-align:top}
table.files td:first-child{white-space:nowrap}
ol.refs li{margin:.4rem 0;font-size:.95rem}
#tip{position:fixed;pointer-events:none;background:var(--tip-bg);color:var(--tip-fg);font:500 .8rem/1.35 var(--body);padding:.35rem .55rem;border-radius:4px;z-index:9;max-width:280px}
@media (prefers-reduced-motion: reduce){*{scroll-behavior:auto}}
"""

JS = """
<script>
(function(){var t=document.getElementById('tip');
function show(e){var s=e.target.getAttribute&&e.target.getAttribute('data-tip');if(!s){t.hidden=true;return}
t.textContent=s;t.hidden=false;var x=e.clientX+14,y=e.clientY+14;var w=t.offsetWidth,h=t.offsetHeight;
if(x+w>innerWidth-8)x=e.clientX-w-14;if(y+h>innerHeight-8)y=e.clientY-h-14;t.style.left=x+'px';t.style.top=y+'px'}
document.addEventListener('mousemove',show);document.addEventListener('touchstart',function(e){show(e.touches[0]&&{target:e.target,clientX:e.touches[0].clientX,clientY:e.touches[0].clientY})},{passive:true});
document.addEventListener('scroll',function(){t.hidden=true},{passive:true});})();
</script>"""


def main():
    kfh, B = build()
    toc = "".join(f'<li><a href="#{i}">{esc(t)}</a></li>' for i, t in [
        ("summary", "Summary"), ("method", "Model and method"), ("replication", "Replicating CGM"), ("trends", "Change over time"),
        ("education", "Education"), ("industry", "Industry"), ("income", "Income level"), ("cohorts", "Birth cohort"),
        ("sources", "SIPP and CPS"), ("parameters", "Model parameters"), ("caveats", "Caveats"), ("sources-list", "Sources")])
    page = f"""<title>US Labor Income Process</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Mono:wght@400;500&family=Source+Sans+3:ital,wght@0,400;0,600;1,400&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header>
<p class="eyebrow">Income Trends · labor income process, 1969-2022</p>
<h1>The US labor income process</h1>
<p class="deck">How household income grows with age, how large its permanent and transitory shocks are, and how both have changed since 1969: CGM (2005) re-estimated on the PSID and checked against SIPP and CPS ASEC.</p>
<p class="meta">Prepared for Richard's life cycle model · October 2026 · PSID 1968-2023, SIPP 1996-2025, CPS ASEC 1988-2026</p>
{kfh}
<nav class="toc" aria-label="Contents"><ol>{toc}</ol></nav>
</header>
<main>{''.join(B)}</main>
</div>
<div id="tip" hidden></div>{JS}
"""
    with open(OUTFILE, "w") as f:
        f.write(page)
    print(OUTFILE, f"{len(page) / 1024:.0f} KB, {FIG[0]} figures, {TAB[0]} tables")


if __name__ == "__main__":
    main()
