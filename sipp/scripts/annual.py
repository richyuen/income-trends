"""Collapse standardized SIPP person-month and job-month frames to person x calendar-year records.

Shared by extract_new.py (2014 panel, SIPP 2018-2025) and extract_old.py (1996-2008 panels).

monthly frame (one row per person-month), required columns:
  panel, pid, year, month, age, byear, sex, race, origin, educ, ms, state, hhsize, famsize, relrp, wgt,
  earn_tot, earn_wage, earn_se, earn_oth, rmesr, weeks_job, hrs_all, typez, imp, imp_dollars, tc
jobs frame (one row per person-month-job), required columns:
  pid, year, month, jobkey, earn, ind, occ, cls, se, hrs, jobid
"""
import numpy as np
import pandas as pd


def _last(df, cols, by):
    """Values of cols at the last observed month of each group (December when observed)."""
    d = df.sort_values(by + ['month']).drop_duplicates(by, keep='last')
    return d[by + cols]


def main_job(jobs):
    """Job with the largest annual earnings in the year (ties: more months, then lowest key).
    Attributes come from the last month of that job in which they are non-missing."""
    if jobs.empty:
        return pd.DataFrame(columns=['pid', 'year', 'main_jobkey', 'main_earn', 'main_months', 'main_ind', 'main_occ',
                                     'main_cls', 'main_se', 'main_hrs', 'main_jobid', 'n_jobs'])
    g = jobs.groupby(['pid', 'year', 'jobkey'], sort=False)
    agg = g.agg(main_earn=('earn', 'sum'), main_months=('month', 'nunique')).reset_index()
    njobs = agg.groupby(['pid', 'year']).size().rename('n_jobs').reset_index()
    agg = agg.sort_values(['pid', 'year', 'main_earn', 'main_months', 'jobkey'],
                          ascending=[True, True, False, False, True]).drop_duplicates(['pid', 'year'])
    js = jobs.merge(agg[['pid', 'year', 'jobkey']], on=['pid', 'year', 'jobkey']).sort_values(['pid', 'year', 'month'])
    attrs = {}
    for c in ['ind', 'occ', 'cls', 'se', 'hrs', 'jobid']:
        s = js[['pid', 'year', c]]
        s = s[s[c].notna() & (s[c].astype(str) != '')]
        attrs[c] = s.drop_duplicates(['pid', 'year'], keep='last').rename(columns={c: 'main_' + c})
    out = agg.rename(columns={'jobkey': 'main_jobkey'})
    for c, s in attrs.items():
        out = out.merge(s, on=['pid', 'year'], how='left')
    return out.merge(njobs, on=['pid', 'year'], how='left')


def annualize(m, jobs, panel, design):
    by = ['pid', 'year']
    m = m.copy()
    m['emp'] = m.rmesr.between(1, 5)
    m['pos'] = m.earn_tot > 0
    m['imp_e'] = m.imp & (m.earn_tot != 0)
    g = m.groupby(by, sort=False)
    a = g.agg(months_obs=('month', 'nunique'), first_month=('month', 'min'), last_month=('month', 'max'),
              earn_tot=('earn_tot', 'sum'), earn_wage=('earn_wage', 'sum'), earn_se=('earn_se', 'sum'),
              earn_oth=('earn_oth', 'sum'), months_earn=('pos', 'sum'), months_emp=('emp', 'sum'),
              weeks_job=('weeks_job', 'sum'), typez_months=('typez', 'sum'), imp_months=('imp_e', 'sum'),
              imp_dollars=('imp_dollars', 'sum'), tc_months=('tc', 'sum'), n_rows=('month', 'size'))
    # average weekly hours (all jobs) over months with a job (new design only; NaN otherwise)
    h = m[m.emp].groupby(by).hrs_all.mean().rename('hrs_all_avg')
    a = a.join(h)
    a = a.reset_index()
    nearn = m[m.earn_tot != 0].groupby(by).size().rename('months_earn_nz').reset_index()
    a = a.merge(nearn, on=by, how='left')
    a['months_earn_nz'] = a.months_earn_nz.fillna(0)
    a['imp_share'] = np.where(a.months_earn_nz > 0, a.imp_months / a.months_earn_nz.where(a.months_earn_nz > 0), np.nan)
    tot_abs = m.assign(ae=m.earn_tot.abs()).groupby(by).ae.sum().rename('abs_earn').reset_index()
    a = a.merge(tot_abs, on=by, how='left')
    a['imp_dollar_share'] = np.where(a.abs_earn > 0, a.imp_dollars / a.abs_earn.where(a.abs_earn > 0), np.nan)
    a['tc_any'] = a.tc_months > 0
    a = a.drop(columns=['abs_earn', 'imp_dollars'])
    last = _last(m, ['age', 'byear', 'sex', 'race', 'origin', 'educ', 'ms', 'state', 'hhsize', 'famsize', 'relrp',
                     'wgt', 'month'], by).rename(columns={'wgt': 'wgt_last', 'month': 'wgt_month'})
    a = a.merge(last, on=by, how='left')
    a = a.merge(main_job(jobs), on=by, how='left')
    a['n_jobs'] = a.n_jobs.fillna(0)
    a['full_year'] = a.months_obs == 12
    a.insert(0, 'design', design)
    a.insert(0, 'panel', panel)
    return a


def educ4(df):
    """1 <HS, 2 HS/GED, 3 some college/assoc/vocational, 4 BA+. Codes differ by design (see README)."""
    e = df.educ
    new = df.design == 'new'
    out = np.select([e < 39, e == 39, new & e.between(40, 42), new & (e >= 43), ~new & e.between(40, 43), ~new & (e >= 44)],
                    [1, 2, 3, 4, 3, 4], default=np.nan)
    return np.where(e.isna() | (e < 0), np.nan, out)


def hisp(df):
    o = df.origin
    old_detail = df.panel.isin([1996, 2001])
    return np.where(o.isna(), np.nan, np.where(old_detail, o.between(20, 28), o == 1)).astype('float32')


def topcode_threshold(values, min_count=5, floor_q=0.99):
    """Heuristic for SIPP's group-mean topcodes: walk down the distinct positive values from the top while each
    value is shared by >= min_count units; the last value passed is the threshold (NaN if the top value is not heaped,
    or if the threshold falls below the floor_q quantile, which would mean round-number heaping, not topcodes)."""
    v = pd.Series(values).dropna()
    v = v[v > 0]
    if v.empty:
        return np.nan
    floor = v.quantile(floor_q)
    vc = v.value_counts().sort_index(ascending=False)
    thr = np.nan
    for val, cnt in vc.items():
        if cnt >= min_count and val >= floor:
            thr = val
        else:
            break
    return thr


def topcode_heap(values, q=0.999, min_count=5):
    """Old panels: topcoded monthly amounts are replaced by cell means, which show up as a heap at the very top.
    Threshold = the most frequent value at or above the q-quantile of positive values (needs >= min_count units);
    NaN if there is no such heap."""
    v = pd.Series(values).dropna()
    v = v[v > 0]
    if v.empty:
        return np.nan
    top = v[v >= v.quantile(q)].value_counts()
    top = top[top >= min_count]
    return float(top.idxmax()) if len(top) else np.nan
