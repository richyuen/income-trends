"""SIPP old design: 1996, 2001, 2004 and 2008 panels, core (longitudinally edited) wave files, monthly person records
(4-month waves, 4 rotation groups). Builds person x calendar-year labor-earnings records.

Usage: python3 -I sipp/scripts/extract_old.py [RAW_DIR] [PANELS...]
  RAW_DIR defaults to /tmp/it_sipp/raw (outside the repo). PANELS default: 1996 2001 2004 2008.
  Each wave zip is deleted after its needed columns are cached in RAW_DIR/../cache_old/ (parquet, ~20-60 MB/wave).
Writes
  sipp/data/sipp_py_old_<panel>.parquet  person-year rows, one file per panel
  sipp/data/sipp_lgtwgt_old.parquet      Census longitudinal (calendar-year and panel) weights, long format
  sipp/output/topcode_thresholds_old.csv detected topcode values of the monthly earnings components
Layouts: 1996 core files on the Census server are the re-edited longitudinal l96puwN files, whose layout is NOT the
posted sip96wNd.asc; positions come from NBER's https://data.nber.org/sipp/1996/sip96l1.dct (same for waves 1-12).
2001/2004/2008 use the Census wave-1 dictionaries (checked on every wave: see checks()).
"""
import io, os, subprocess, sys, zipfile
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from annual import annualize, educ4, hisp, topcode_heap  # noqa: E402
from layouts import census_layout, nber_layout  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..'))
DATA = os.path.join(ROOT, 'data'); OUT = os.path.join(ROOT, 'output')
args = [a for a in sys.argv[1:] if not a.startswith('--')]
RAW = args[0] if args else '/tmp/it_sipp/raw'
CACHE = os.path.join(os.path.dirname(os.path.abspath(RAW)), 'cache_old')
SEL = [int(p) for p in args[1:]] or [1996, 2001, 2004, 2008]
B = 'https://www2.census.gov/programs-surveys/sipp/data/datasets'
for d in (RAW, CACHE, DATA, OUT):
    os.makedirs(d, exist_ok=True)

# panel -> (n waves, dictionary (url, kind), core zip pattern, longitudinal weight (zip, dictionary), CY1 year,
#           final panel weight name, industry/occupation code systems)
PANELS = {
    1996: (12, ('https://data.nber.org/sipp/1996/sip96l1.dct', 'nber'), '1996/w{w}/l96puw{w}.zip',
           ('1996/ctl_fer.zip', '1996/ctl_ferd.asc'), 1996, 'LGTPNLWT', 'Census 1990 IND', 'Census 1990 OCC'),
    2001: (9, (f'{B}/2001/w1/l01puw1d.txt', 'census'), '2001/w{w}/l01puw{w}.zip',
           ('2001/w9/lgtwgt2001w9.zip', '2001/lgtwt01d.txt'), 2001, 'LGTPNWT3', 'Census 1990 IND', 'Census 1990 OCC'),
    2004: (12, (f'{B}/2004/w1/l04puw1d.txt', 'census'), '2004/w{w}/l04puw{w}.zip',
           ('2004/w12/lgtwgt2004w12.zip', '2004/w12/lgt04w12d.txt'), 2004, 'LGTPNWT4', 'Census 2002 IND',
           'Census 2000 OCC'),
    2008: (16, (f'{B}/2008/w1/l08puw1d.txt.old2', 'census'), '2008/w{w}/l08puw{w}.zip',
           ('2008/w16/lgtwgt2008w16.zip', '2008/w16/lgtwgt2008w16.txt'), 2009, 'LGTPN5WT', 'Census 2002 IND',
           'Census 2000 OCC'),
}
VARS = ('SSUID SPANEL SWAVE SREFMON RHCALMN RHCALYR EPPPNUM EPPINTVW EPOPSTAT TBYEAR ESEX ERACE EORIGIN WPFINWGT TAGE '
        'ERRP EMS EEDUCATE TFIPSST EHHNUMPP EFNP TPEARN TPMSUM1 TPMSUM2 APMSUM1 APMSUM2 TBMSUM1 TBMSUM2 ABMSUM1 '
        'ABMSUM2 TMLMSUM AMLMSUM EJBIND1 EJBIND2 TJBOCC1 TJBOCC2 ECLWRK1 ECLWRK2 EJBHRS1 EJBHRS2 EHRSBS1 EHRSBS2 '
        'TBSIND1 TBSIND2 TBSOCC1 TBSOCC2 EENO1 EENO2 EBNO1 EBNO2 RMESR RMWKWJB').split()
STR = {'SSUID', 'EJBIND1', 'EJBIND2', 'TJBOCC1', 'TJBOCC2', 'TBSIND1', 'TBSIND2', 'TBSOCC1', 'TBSOCC2', 'TFIPSST'}
IMP_OLD = {1, 2, 4}  # allocation flags: 1 hot deck, 2 cold deck, 4 statistical/logical from previous wave (3 logical = not)


def fetch(url, name):
    p = os.path.join(RAW, name)
    if not os.path.exists(p):
        print('download', url, flush=True)
        subprocess.run(['curl', '-sS', '-f', '--retry', '5', '-o', p + '.part', url], check=True)
        os.rename(p + '.part', p)
    return p


def read_fixed(zpath, pos, block=50_000):
    """Fixed-width reader: numpy byte matrix per block of records, columns sliced by position."""
    z = zipfile.ZipFile(zpath)
    name = [n for n in z.namelist() if not n.endswith('/')][0]
    out = []
    with z.open(name) as f:
        first = f.readline()
        reclen = len(first)  # includes the newline
        f2 = z.open(name)
        while True:
            buf = f2.read(reclen * block)
            if not buf:
                break
            n = len(buf) // reclen
            assert n * reclen == len(buf), 'ragged records'
            arr = np.frombuffer(buf, dtype='u1').reshape(n, reclen)
            cols = {}
            for k, (s, w) in pos.items():
                sl = np.ascontiguousarray(arr[:, s:s + w]).view(f'S{w}').ravel()
                if k in STR:
                    cols[k] = pd.Series(sl).str.decode('latin-1').str.strip()
                else:
                    try:
                        cols[k] = sl.astype('float64')
                    except ValueError:
                        cols[k] = pd.to_numeric(pd.Series(sl).str.decode('latin-1').str.strip(), errors='coerce').to_numpy()
            out.append(pd.DataFrame(cols))
        f2.close()
    return pd.concat(out, ignore_index=True)


def checks(d, panel, w):
    assert (d.SWAVE == w).all(), (panel, w, 'SWAVE', d.SWAVE.unique()[:5])
    assert (d.SPANEL == panel).all(), (panel, w, 'SPANEL')
    assert d.EPPPNUM.between(101, 2999).all(), (panel, w, 'EPPPNUM')
    assert d.SREFMON.between(1, 4).all() and d.RHCALMN.between(1, 12).all(), (panel, w, 'months')
    assert d.RHCALYR.between(panel - 1, panel + 6).all(), (panel, w, 'RHCALYR')
    a = d[d.EPOPSTAT == 1]
    comp = a[['TPMSUM1', 'TPMSUM2', 'TBMSUM1', 'TBMSUM2', 'TMLMSUM']].sum(axis=1)
    # TPEARN = jobs + business draws + moonlighting, plus (2004/2008) unincorporated-business profit spread over months
    ok = (np.isclose(a.TPEARN, comp, atol=1) | (a.EBNO1 > 0) | (a.EBNO2 > 0)).mean()
    agesane = a.TAGE.between(15, 90).mean()
    print(f'  {panel} w{w}: rows {len(d)}, adults {len(a)}, TPEARN==sum(components) {ok:.4f}, age15-90 {agesane:.4f}, '
          f'months {int(d.RHCALYR.min())}/{int(d.RHCALMN[d.RHCALYR == d.RHCALYR.min()].min())}-'
          f'{int(d.RHCALYR.max())}/{int(d.RHCALMN[d.RHCALYR == d.RHCALYR.max()].max())}', flush=True)
    assert ok > 0.97 and agesane > 0.99, (panel, w, 'layout check failed', ok, agesane)
    return ok


def wave(panel, w, pos):
    cache = os.path.join(CACHE, f'core_{panel}_w{w}.parquet')
    if os.path.exists(cache):
        return pd.read_parquet(cache)
    pat = PANELS[panel][2]
    z = fetch(f'{B}/{pat.format(w=w)}', os.path.basename(pat.format(w=w)))
    d = read_fixed(z, pos)
    d['ok_share'] = checks(d, panel, w)
    for c in d.columns:
        if d[c].dtype == 'float64' and c not in ('TPEARN', 'TPMSUM1', 'TPMSUM2', 'TBMSUM1', 'TBMSUM2', 'TMLMSUM'):
            d[c] = d[c].astype('float32')
    d.to_parquet(cache, index=False)
    os.remove(z)
    return d


def build(panel):
    nw, (durl, kind), pat, lgt, cy1, pnlwt, ivint, ovint = PANELS[panel]
    dpath = fetch(durl, f'dict_{panel}_' + os.path.basename(durl))
    pos = (nber_layout if kind == 'nber' else census_layout)(dpath, set(VARS))
    miss = set(VARS) - set(pos)
    assert not miss, (panel, miss)
    months, jobs, okl = [], [], []
    for w in range(1, nw + 1):
        d = wave(panel, w, pos)
        okl.append((w, float(d.ok_share.iloc[0])))
        d = d.drop(columns='ok_share')
        if d.WPFINWGT.median() > 1e5:      # 4 implied decimals in the fixed-width files
            d['WPFINWGT'] = d.WPFINWGT / 1e4
        # residual of TPEARN over the components (business profit/loss): to the person's business that month
        # (business 1 if present, else 2); if no business, to "other" earnings
        resid = (d.TPEARN - d[['TPMSUM1', 'TPMSUM2', 'TBMSUM1', 'TBMSUM2', 'TMLMSUM']].sum(axis=1)).to_numpy()
        resid = np.where(np.abs(resid) <= 1, 0, resid)
        bslot = np.where(d.EBNO1 > 0, 1, np.where(d.EBNO2 > 0, 2, 0))
        d['pid'] = d.SSUID.str.zfill(12) + '_' + d.EPPPNUM.astype('int64').astype(str)
        d['year'] = d.RHCALYR.astype('int16'); d['month'] = d.RHCALMN.astype('int8')
        imp = np.zeros(len(d), bool); impd = np.zeros(len(d))
        for v, a in [('TPMSUM1', 'APMSUM1'), ('TPMSUM2', 'APMSUM2'), ('TBMSUM1', 'ABMSUM1'), ('TBMSUM2', 'ABMSUM2'),
                     ('TMLMSUM', 'AMLMSUM')]:
            f = d[a].isin(IMP_OLD).to_numpy() & (d[v] != 0).to_numpy()
            imp |= f; impd += np.where(f, d[v].abs(), 0)
        typez = d.EPPINTVW.isin([3, 4]).to_numpy()
        impd = np.where(typez, d.TPEARN.abs(), impd)
        m = pd.DataFrame({'pid': d.pid, 'year': d.year, 'month': d.month, 'swave': np.float32(w),
                          'age': d.TAGE, 'byear': d.TBYEAR, 'sex': d.ESEX, 'race': d.ERACE, 'origin': d.EORIGIN,
                          'educ': d.EEDUCATE, 'ms': d.EMS, 'state': d.TFIPSST, 'hhsize': d.EHHNUMPP,
                          'famsize': d.EFNP, 'relrp': d.ERRP, 'wgt': d.WPFINWGT, 'earn_tot': d.TPEARN,
                          'earn_wage': d.TPMSUM1 + d.TPMSUM2, 'earn_se': d.TBMSUM1 + d.TBMSUM2 + np.where(bslot > 0, resid, 0),
                          'earn_oth': d.TMLMSUM + np.where(bslot == 0, resid, 0),
                          'rmesr': d.RMESR, 'weeks_job': d.RMWKWJB, 'hrs_all': np.float32(np.nan),
                          'typez': typez, 'imp': imp | typez, 'imp_dollars': impd,
                          'mx_wage': d[['TPMSUM1', 'TPMSUM2']].max(axis=1), 'mx_se': d[['TBMSUM1', 'TBMSUM2']].max(axis=1),
                          'mx_oth': d.TMLMSUM})
        months.append(m)
        for k in (1, 2):
            jj = d[(d[f'EENO{k}'] > 0) | (d[f'TPMSUM{k}'] != 0)]
            jobs.append(pd.DataFrame({'pid': jj.pid, 'year': jj.year, 'month': jj.month,
                                      'jobkey': jj[f'EENO{k}'].fillna(-k).astype('int16'), 'earn': jj[f'TPMSUM{k}'],
                                      'ind': jj[f'EJBIND{k}'], 'occ': jj[f'TJBOCC{k}'], 'cls': jj[f'ECLWRK{k}'],
                                      'se': np.float32(0), 'hrs': jj[f'EJBHRS{k}'], 'jobid': jj[f'EENO{k}']}))
            d['_be'] = d[f'TBMSUM{k}'] + np.where(bslot == k, resid, 0)
            bb = d[(d[f'EBNO{k}'] > 0) | (d._be != 0)]
            jobs.append(pd.DataFrame({'pid': bb.pid, 'year': bb.year, 'month': bb.month,
                                      'jobkey': (100 + bb[f'EBNO{k}'].fillna(-k)).astype('int16'), 'earn': bb._be,
                                      'ind': bb[f'TBSIND{k}'], 'occ': bb[f'TBSOCC{k}'], 'cls': np.float32(np.nan),
                                      'se': np.float32(1), 'hrs': bb[f'EHRSBS{k}'], 'jobid': bb[f'EBNO{k}']}))
        del d
    m = pd.concat(months, ignore_index=True); del months
    jb = pd.concat(jobs, ignore_index=True); del jobs
    for c in ('ind', 'occ'):
        jb[c] = jb[c].where(~jb[c].isin(['-1', '-01', '-001', '0', '00', '000', '0000', '']))
    jb['hrs'] = jb.hrs.where(jb.hrs > 0)
    jb['cls'] = jb.cls.where(jb.cls > 0)
    # Records can repeat a calendar month only if a person appears twice in a wave; keep one
    dup = m.duplicated(['pid', 'year', 'month'])
    if dup.any():
        print(panel, 'duplicate person-months dropped:', int(dup.sum()))
        m = m[~dup]
    jb = jb.drop_duplicates(['pid', 'year', 'month', 'jobkey'])
    # topcodes: heaped values at the top of each monthly component
    thr = {}
    for c in ('mx_wage', 'mx_se', 'mx_oth'):
        thr[c] = topcode_heap(m[['pid', c]].drop_duplicates()[c])
    # Topcodes are cell means of one common monthly cap for all components; use the lowest detected heap for all three
    thr['common'] = np.nanmin(list(thr.values())) if any(~np.isnan(v) for v in thr.values()) else np.nan
    tc = np.zeros(len(m), bool)
    if not np.isnan(thr['common']):
        for c in ('mx_wage', 'mx_se', 'mx_oth'):
            tc |= (m[c] >= thr['common']).to_numpy()
    m['tc'] = tc
    m = m.drop(columns=['mx_wage', 'mx_se', 'mx_oth'])
    for c in ('age', 'byear', 'sex', 'race', 'origin', 'educ', 'ms', 'hhsize', 'famsize', 'relrp'):
        m[c] = m[c].where(m[c] >= 0)
    a = annualize(m, jb, panel, 'old')
    sw = m.groupby(['pid', 'year']).swave.agg(['min', 'max']).rename(columns={'min': 'wave_first', 'max': 'wave_last'})
    a = a.merge(sw.reset_index(), on=['pid', 'year'], how='left')
    a = a[a.age.fillna(0) >= 15].copy()
    a['ind_vintage'] = ivint; a['occ_vintage'] = ovint
    a['source_file'] = f'{panel} core waves 1-{nw}'
    a['educ4'] = educ4(a); a['hisp'] = hisp(a)
    # longitudinal weights
    w = lgtweights(panel, lgt, cy1)
    wl = w.copy()
    cy = w[w.wt_name.str.startswith('LGTCY')][['pid', 'first_year', 'weight']].rename(
        columns={'first_year': 'year', 'weight': 'lgtwt_cy'})
    a = a.merge(cy, on=['pid', 'year'], how='left')
    pn = w[w.wt_name == pnlwt][['pid', 'weight']].rename(columns={'weight': 'lgtwt_pnl'})
    a = a.merge(pn, on='pid', how='left')
    a['lgtwt_pnl_span'] = f'{pnlwt} (panel, Census lgtwgt file)'
    a = a.sort_values(['pid', 'year'])
    a.to_parquet(os.path.join(DATA, f'sipp_py_old_{panel}.parquet'), index=False, compression='zstd')
    print(panel, 'person-years 15+:', len(a), 'years', a.groupby('year').size().to_dict(), 'thresholds', thr, flush=True)
    return thr, wl


def lgtweights(panel, lgt, cy1):
    zrel, drel = lgt
    dp = fetch(f'{B}/{drel}', f'dict_{panel}_lgt.txt')
    pos = census_layout(dp)
    zp = fetch(f'{B}/{zrel}', f'lgt_{panel}.zip')
    STR.update({'LGTKEY'})
    d = read_fixed(zp, pos, block=200_000)
    d['pid'] = d.SSUID.str.zfill(12) + '_' + d.EPPPNUM.astype('int64').astype(str)
    for c in [c for c in pos if c.startswith('LGT') and c != 'LGTKEY']:
        if d[c][d[c] > 0].median() > 1e5:   # 4 implied decimals
            d[c] = d[c] / 1e4
    rows = []
    for c in [c for c in pos if c.startswith('LGT') and c != 'LGTKEY']:
        if c.startswith('LGTCY'):
            k = int(c[5]); y0 = y1 = cy1 + k - 1
        else:
            y0, y1 = None, None
        rows.append(pd.DataFrame({'panel': np.int16(panel), 'pid': d.pid, 'wt_name': c, 'wt_file': os.path.basename(zrel),
                                  'first_year': y0, 'last_year': y1, 'weight': d[c].astype('float32')}))
    os.remove(zp)
    return pd.concat(rows, ignore_index=True)


if __name__ == '__main__':
    thrs, wts = [], []
    for p in SEL:
        t, w = build(p)
        thrs += [{'panel': p, 'component': k, 'threshold': v} for k, v in t.items()]
        wts.append(w)
    tp = os.path.join(OUT, 'topcode_thresholds_old.csv')
    t = pd.DataFrame(thrs)
    if os.path.exists(tp):
        old = pd.read_csv(tp); t = pd.concat([old[~old.panel.isin(SEL)], t])
    t.to_csv(tp, index=False)
    wp = os.path.join(DATA, 'sipp_lgtwgt_old.parquet')
    w = pd.concat(wts, ignore_index=True)
    if os.path.exists(wp):
        old = pd.read_parquet(wp); w = pd.concat([old[~old.panel.isin(SEL)], w], ignore_index=True)
    w.to_parquet(wp, index=False, compression='zstd')
