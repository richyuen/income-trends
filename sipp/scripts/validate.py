"""Validation tables for the SIPP person-year files.

Usage: python3 -I sipp/scripts/validate.py [CACHE_OLD_DIR]
  CACHE_OLD_DIR (default /tmp/it_sipp/cache_old) holds the per-wave old-panel extracts written by extract_old.py; used
  only for the seam-effect check (skipped if absent).
Writes to sipp/output/:
  validation_panel_year.csv  persons, 12-month persons, weighted 12-month earners 25-64, weighted mean/median earnings
                             (all, men, women), imputation and topcode shares, Type-Z share
  linkage_panel_year.csv     share of person-year records with a record for the same person in year+1 (same panel)
  population_check.csv       weighted December population 16+ vs BLS civilian noninstitutional population 16+
                             (FRED CNP16OV, December), by Census file
  seam_old_panels.csv        month-to-month change in earnings at wave seams vs within waves (old panels)
"""
import glob, os, subprocess, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
DATA = os.path.join(ROOT, 'data'); OUT = os.path.join(ROOT, 'output')
CACHE = sys.argv[1] if len(sys.argv) > 1 else '/tmp/it_sipp/cache_old'


def wmedian(x, w):
    o = np.argsort(x); x = np.asarray(x)[o]; w = np.asarray(w)[o]
    c = np.cumsum(w)
    return x[np.searchsorted(c, c[-1] / 2)]


def load():
    fs = sorted(glob.glob(os.path.join(DATA, 'sipp_py_*.parquet')))
    a = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    return a


def panel_year(a):
    rows = []
    for (p, y), g in a.groupby(['panel', 'year']):
        e = g[(g.months_obs == 12) & g.age.between(25, 64) & (g.earn_tot > 0) & (g.wgt_last > 0)]
        r = {'panel': p, 'year': y, 'design': g.design.iloc[0], 'source_files': ';'.join(sorted(g.source_file.unique())),
             'persons_15plus': len(g), 'persons_12m': int((g.months_obs == 12).sum()),
             'share_12m': round((g.months_obs == 12).mean(), 3),
             'n_12m_earners_25_64': len(e), 'wtd_12m_earners_25_64_mil': round(e.wgt_last.sum() / 1e6, 2)}
        for lab, s in [('all', e), ('men', e[e.sex == 1]), ('women', e[e.sex == 2])]:
            r[f'mean_{lab}'] = round(np.average(s.earn_tot, weights=s.wgt_last)) if len(s) else np.nan
            r[f'median_{lab}'] = round(wmedian(s.earn_tot.to_numpy(), s.wgt_last.to_numpy())) if len(s) else np.nan
        if len(e):
            r['imp_any_share'] = round((e.imp_months > 0).mean(), 3)
            r['imp_dollar_share_wtd'] = round(np.average(e.imp_dollar_share.fillna(0), weights=e.wgt_last * e.earn_tot), 3)
            r['typez_share'] = round((e.typez_months > 0).mean(), 3)
            r['tc_any_share'] = round(e.tc_any.mean(), 4)
            r['se_share'] = round((e.earn_se != 0).mean(), 3)
        r['wtd_15plus_dec_mil'] = round(g.loc[g.wgt_month == 12, 'wgt_last'].sum() / 1e6, 1)
        rows.append(r)
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, 'validation_panel_year.csv'), index=False)
    return t


def linkage(a):
    k = a[['panel', 'pid', 'year', 'months_obs', 'age', 'earn_tot']]
    nxt = k[['panel', 'pid', 'year', 'months_obs']].assign(year=k.year - 1).rename(columns={'months_obs': 'm_next'})
    j = k.merge(nxt, on=['panel', 'pid', 'year'], how='left')
    rows = []
    last = a.groupby('panel').year.max()
    for (p, y), g in j.groupby(['panel', 'year']):
        e = g[(g.months_obs == 12) & g.age.between(25, 64) & (g.earn_tot > 0)]
        rows.append({'panel': p, 'year': y, 'last_year_of_panel': int(y == last[p]), 'records': len(g),
                     'linked_next_year': round(g.m_next.notna().mean(), 3),
                     'linked_next_12m': round((g.m_next == 12).mean(), 3),
                     'earners25_64_12m_linked_next_12m': round((e.m_next == 12).mean(), 3) if len(e) else np.nan})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, 'linkage_panel_year.csv'), index=False)
    return t


def population(a):
    p = os.path.join(DATA, 'fred_cnp16ov.csv')
    if not os.path.exists(p):
        subprocess.run(['curl', '-sS', '-f', '-o', p, 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=CNP16OV'],
                       check=True)
    c = pd.read_csv(p)
    c['date'] = pd.to_datetime(c.observation_date)
    dec = c[c.date.dt.month == 12].assign(year=lambda d: d.date.dt.year).set_index('year').CNP16OV / 1000
    rows = []
    d = a[(a.wgt_month == 12) & (a.age >= 16)]
    # new design: weights of one Census file (all its panels) add up to the population; old: each panel does
    d = d.assign(unit=np.where(d.design == 'new', d.source_file, d.panel.astype(str)))
    for (u, y), g in d.groupby(['unit', 'year']):
        rows.append({'unit': u, 'year': y, 'panels': ','.join(map(str, sorted(g.panel.unique()))),
                     'sipp_dec_pop16plus_mil': round(g.wgt_last.sum() / 1e6, 1),
                     'bls_cnp16ov_dec_mil': round(dec.get(y, np.nan), 1),
                     'ratio': round(g.wgt_last.sum() / 1e6 / dec.get(y, np.nan), 3)})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, 'population_check.csv'), index=False)
    return t


def seam():
    fs = sorted(glob.glob(os.path.join(CACHE, 'core_*_w*.parquet')))
    if not fs:
        print('no old-panel cache; seam check skipped'); return None
    rows = []
    for panel in sorted({os.path.basename(f).split('_')[1] for f in fs}):
        parts = []
        for f in [f for f in fs if f'core_{panel}_' in f]:
            d = pd.read_parquet(f, columns=['SSUID', 'EPPPNUM', 'SWAVE', 'RHCALYR', 'RHCALMN', 'EPOPSTAT', 'TPEARN'])
            parts.append(d[d.EPOPSTAT == 1])
        d = pd.concat(parts).assign(t=lambda x: x.RHCALYR * 12 + x.RHCALMN).sort_values(['SSUID', 'EPPPNUM', 't'])
        prev = d.groupby(['SSUID', 'EPPPNUM']).shift(1)
        ok = (prev.t == d.t - 1)
        seamflag = (prev.SWAVE != d.SWAVE)
        both = ok & ((d.TPEARN != 0) | (prev.TPEARN != 0))
        ch = (d.TPEARN != prev.TPEARN)
        for lab, msk in [('within_wave', both & ~seamflag), ('at_seam', both & seamflag)]:
            rows.append({'panel': panel, 'pair': lab, 'n_pairs': int(msk.sum()),
                         'share_earnings_changed': round(ch[msk].mean(), 3),
                         'share_job_start_or_stop': round(((d.TPEARN == 0) != (prev.TPEARN == 0))[msk].mean(), 4)})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT, 'seam_old_panels.csv'), index=False)
    return t


if __name__ == '__main__':
    a = load()
    print('rows', len(a))
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
    print(panel_year(a).to_string())
    print(linkage(a).to_string())
    print(population(a).to_string())
    print(seam())
