"""SIPP new design: 2014 panel (waves 1-4 = reference years 2013-2016) and SIPP files 2018-2025 (reference year =
file year - 1; each file holds several panels, SPANEL). Builds person x calendar-year labor-earnings records.

Usage: python3 -I sipp/scripts/extract_new.py [RAW_DIR] [FILES...]
  RAW_DIR defaults to /tmp/it_sipp/raw (outside the repo). FILES are keys like 2014w1 ... 2014w4 2018 ... 2025
  (default: all). Each zip is deleted after extraction.
Writes
  sipp/data/new/sipp_py_<file>.parquet   intermediate person-year rows per Census file (kept for reruns)
  sipp/data/sipp_py_new_<panel>.parquet  final person-year rows, one file per panel (run combine step: --combine)
  sipp/data/sipp_lgtwgt_new.parquet      all Census longitudinal weights for the new design (long format)
  sipp/output/topcode_thresholds_new.csv detected topcode values of the pay-rate inputs
Source: https://www2.census.gov/programs-surveys/sipp/data/datasets/{2014/wN|YYYY}/
"""
import io, json, os, subprocess, sys, zipfile
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pc

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from annual import annualize, educ4, hisp, topcode_threshold  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..'))
DATA = os.path.join(ROOT, 'data'); OUT = os.path.join(ROOT, 'output'); INTER = os.path.join(DATA, 'new')
args = [a for a in sys.argv[1:] if not a.startswith('--')]
RAW = args[0] if args else '/tmp/it_sipp/raw'
B = 'https://www2.census.gov/programs-surveys/sipp/data/datasets'
for d in (RAW, DATA, OUT, INTER):
    os.makedirs(d, exist_ok=True)

FILES = {f'2014w{w}': (f'2014/w{w}', f'pu2014w{w}', 2012 + w) for w in (1, 2, 3, 4)}
FILES.update({str(y): (str(y), f'pu{y}', y - 1) for y in range(2018, 2026)})
SEL = args[1:] or list(FILES)

PAYTYPES = {'ANNSAL': 3, 'HOURLY': 3, 'WKLY': 3, 'BWKLY': 3, 'MTHLY': 3, 'SMTHLY': 3, 'OTHER': 3, 'GAMT': 1, 'PRFTB': 0}
IMP = {2, 4, 5, 6, 7, 8}   # status flags: 2 hot deck, 4 model, 5 cold deck, 6 range, 7/8 combinations (3 logical = not)
PERSON = ['SSUID', 'PNUM', 'SPANEL', 'SWAVE', 'MONTHCODE', 'ERESIDENCEID', 'RIN_UNIV', 'WPFINWGT', 'TAGE', 'TAGE_EHC',
          'TDOB_BYEAR', 'ESEX', 'ERACE', 'EORIGIN', 'EEDUC', 'EMS', 'ERELRPE', 'RHNUMPER', 'RFAMNUM', 'TEHC_ST',
          'TST_INTV', 'EINTTYPE', 'TPEARN', 'RMESR', 'RMWKWJB', 'TMWKHRS']


def job_cols(j):
    c = [f'TJB{j}_MSUM', f'EJB{j}_JBORSE', f'EJB{j}_CLWRK', f'TJB{j}_IND', f'TJB{j}_OCC', f'TJB{j}_JOBHRS1',
         f'EJB{j}_JOBID']
    for t, k in PAYTYPES.items():
        items = [t] if k == 0 else [f'{t}{i}' for i in range(1, k + 1)]
        for it in items:
            c += [f'TJB{j}_{it}', f'AJB{j}_{it}']
    return c


def fetch(rel, name):
    p = os.path.join(RAW, name)
    if not os.path.exists(p):
        print('download', rel, flush=True)
        subprocess.run(['curl', '-sS', '-f', '--retry', '5', '-o', p + '.part', f'{B}/{rel}'], check=True)
        os.rename(p + '.part', p)
    return p


def read_file(key):
    rel, stem, ref = FILES[key]
    sch = json.load(open(fetch(f'{rel}/{stem}_schema.json', f'{stem}_schema.json')))
    dtype = {v['name'].upper(): v['dtype'] for v in sch}
    want = PERSON + [c for j in range(1, 8) for c in job_cols(j)]
    zpath = fetch(f'{rel}/{stem}_csv.zip', f'{stem}_csv.zip')
    z = zipfile.ZipFile(zpath)
    member = [n for n in z.namelist() if n.lower().endswith('.csv')][0]
    with z.open(member) as f:
        header = f.readline().decode('latin-1').strip().split('|')
    hmap = {h.upper(): h for h in header}
    cols = [hmap[c] for c in want if c in hmap]
    missing = [c for c in want if c not in hmap]
    if missing:
        print(key, 'missing columns:', missing[:20], len(missing), flush=True)
    ctypes = {hmap[c]: (pa.string() if dtype.get(c) == 'string' or c == 'SSUID' else pa.float64()) for c in want if c in hmap}
    months, jobs = [], []
    with z.open(member) as f:
        rd = pc.open_csv(f, read_options=pc.ReadOptions(block_size=1 << 25),
                         parse_options=pc.ParseOptions(delimiter='|'),
                         convert_options=pc.ConvertOptions(include_columns=cols, column_types=ctypes))
        for batch in rd:
            d = batch.to_pandas()
            d.columns = [c.upper() for c in d.columns]
            for c in want:
                if c not in d:
                    d[c] = np.nan
            d['pid'] = d.SSUID + '_' + d.PNUM.astype('int64').astype(str)
            mo = pd.DataFrame({'pid': d.pid, 'panel': d.SPANEL.astype('int16'), 'month': d.MONTHCODE.astype('int8')})
            wage = np.zeros(len(d)); oth = np.zeros(len(d))
            impd = np.zeros(len(d)); imp = np.zeros(len(d), bool)
            # TPEARN = job earnings (TJBn_MSUM) + business profit/loss spread over the months; the profit/loss part
            # (residual) is assigned to the person's self-employment job: first SE slot with nonzero TJBn_PRFTB, else
            # first SE slot.
            tpearn = d.TPEARN.fillna(0).to_numpy()
            msum = d[[f'TJB{j}_MSUM' for j in range(1, 8)]].fillna(0).sum(axis=1).to_numpy()
            resid = tpearn - msum
            slot_p = np.zeros(len(d), 'int8'); slot_a = np.zeros(len(d), 'int8')
            for j in range(7, 0, -1):          # descending, so the lowest qualifying slot wins
                isse = (d[f'EJB{j}_JBORSE'] == 2).to_numpy()
                slot_a = np.where(isse, j, slot_a)
                slot_p = np.where(isse & (d[f'TJB{j}_PRFTB'].fillna(0) != 0).to_numpy(), j, slot_p)
            se_slot = np.where(slot_p > 0, slot_p, slot_a)
            for j in range(1, 8):
                e = d[f'TJB{j}_MSUM']
                held = d[f'EJB{j}_JBORSE'].notna() | (e.fillna(0) != 0)
                if not held.any():
                    continue
                ef = e.fillna(0).to_numpy() + np.where(se_slot == j, resid, 0)
                jb = d[f'EJB{j}_JBORSE']
                wage += np.where(jb == 1, ef, 0)
                oth += np.where((jb != 1) & (jb != 2), ef, 0)
                fl = np.zeros(len(d), bool)
                tc = {}
                for t, k in PAYTYPES.items():
                    items = [t] if k == 0 else [f'{t}{i}' for i in range(1, k + 1)]
                    fl |= d[[f'AJB{j}_{it}' for it in items]].isin(IMP).any(axis=1).to_numpy()
                    tc['pay_' + t] = d[[f'TJB{j}_{it}' for it in items]].max(axis=1).astype('float32')
                fl &= (ef != 0)
                imp |= fl; impd += np.where(fl, np.abs(ef), 0)
                jd = pd.DataFrame({'pid': d.pid, 'month': mo.month, 'jobkey': np.int8(j), 'earn': ef.astype('float64'),
                                   'ind': d[f'TJB{j}_IND'], 'occ': d[f'TJB{j}_OCC'], 'cls': d[f'EJB{j}_CLWRK'],
                                   'se': (jb == 2).astype('float32').where(jb.notna()), 'jborse': jb,
                                   'hrs': d[f'TJB{j}_JOBHRS1'], 'jobid': d[f'EJB{j}_JOBID'], 'imp': fl, **tc})
                jobs.append(jd[held.to_numpy()])
            age = d.TAGE_EHC.where(d.TAGE_EHC.notna(), d.TAGE)
            mo = mo.assign(age=age.astype('float32'), byear=d.TDOB_BYEAR.astype('float32'), sex=d.ESEX.astype('float32'),
                           race=d.ERACE.astype('float32'), origin=d.EORIGIN.astype('float32'),
                           educ=d.EEDUC.astype('float32'), ms=d.EMS.astype('float32'),
                           state=d.TEHC_ST.where(d.TEHC_ST.notna() & (d.TEHC_ST != ''), d.TST_INTV),
                           hhsize=d.RHNUMPER.astype('float32'), relrp=d.ERELRPE.astype('float32'),
                           wgt=d.WPFINWGT.astype('float32'), earn_tot=d.TPEARN.fillna(0).astype('float64'),
                           earn_wage=wage, earn_oth=oth + np.where(se_slot == 0, resid, 0),
                           earn_se=tpearn - wage - oth - np.where(se_slot == 0, resid, 0), rmesr=d.RMESR.astype('float32'),
                           weeks_job=d.RMWKWJB.astype('float32'), hrs_all=d.TMWKHRS.astype('float32'),
                           typez=(d.EINTTYPE == 3).to_numpy(), imp=imp, imp_dollars=impd,
                           in_univ=(d.RIN_UNIV.fillna(1) == 1).to_numpy(),
                           resid=d.ERESIDENCEID.astype(str), famnum=d.RFAMNUM.astype('float32'),
                           ssuid=d.SSUID, swave=d.SWAVE.astype('float32'))
            months.append(mo)
    m = pd.concat(months, ignore_index=True)
    jb = pd.concat(jobs, ignore_index=True)
    return m, jb, ref


def process(key):
    m, jb, ref = read_file(key)
    m['year'] = np.int16(ref); jb['year'] = np.int16(ref)
    # family size: persons sharing household (SSUID x residence) and family number in the month
    fs = m[m.famnum.notna()].groupby(['ssuid', 'resid', 'famnum', 'month']).size().rename('famsize').reset_index()
    m = m.merge(fs, on=['ssuid', 'resid', 'famnum', 'month'], how='left')
    m['famsize'] = m.famsize.astype('float32')
    # topcode thresholds of the pay-rate inputs (group-mean topcodes, detected from heaping at the top)
    thr = {}
    for t in PAYTYPES:
        u = jb[['pid', 'jobkey', 'pay_' + t]].dropna().drop_duplicates()
        thr[t] = topcode_threshold(u['pay_' + t])
    tcj = np.zeros(len(jb), bool)
    for t, v in thr.items():
        if not np.isnan(v):
            tcj |= (jb['pay_' + t] >= v).to_numpy()
    jb['tc'] = tcj
    tcm = jb[jb.tc].groupby(['pid', 'month']).size().rename('tcn').reset_index()
    m = m.merge(tcm, on=['pid', 'month'], how='left')
    m['tc'] = m.tcn.fillna(0) > 0
    # Rows outside the survey frame (RIN_UNIV=2: institutionalized/abroad that month) are not counted as observed
    nout = int((~m.in_univ).sum())
    m = m[m.in_univ]
    panels = []
    for p, mp in m.groupby('panel'):
        jp = jb[jb.pid.isin(set(mp.pid))]
        a = annualize(mp, jp, int(p), 'new')
        sw = mp.groupby('pid').swave.max().rename('swave').reset_index()
        a = a.merge(sw, on='pid', how='left')
        panels.append(a)
    a = pd.concat(panels, ignore_index=True)
    a = a[a.age.fillna(0) >= 15].copy()
    a['source_file'] = FILES[key][1]
    a.to_parquet(os.path.join(INTER, f'sipp_py_{key}.parquet'), index=False)
    pd.DataFrame([{'file': key, 'type': t, 'threshold': v} for t, v in thr.items()]).to_csv(
        os.path.join(INTER, f'topcode_{key}.csv'), index=False)
    print(key, 'ref', ref, 'person-years 15+:', len(a), 'rows outside frame dropped:', nout,
          'panels:', a.panel.value_counts().sort_index().to_dict(), flush=True)
    os.remove(os.path.join(RAW, FILES[key][1] + '_csv.zip'))


LGT = [('2014/w2', 'lgtwgt2014pnl2.csv.gz', 2014, 2013, 2014), ('2014/w3', 'lgtwgt2014pnl3.csv.gz', 2014, 2013, 2015),
       ('2014/w4', 'lgtwgt2014pnl4.csv.gz', 2014, 2013, 2016), ('2019', 'lgtwgt2019_csv.zip', None, 2017, 2018)]
LGT += [(str(y), f'lgtwgt{y}yr{k}_csv.zip', None, y - k, y - 1) for y in range(2020, 2026) for k in (2, 3, 4)]


def lgtwgt():
    rows = []
    for rel, name, panel, y0, y1 in LGT:
        try:
            p = fetch(f'{rel}/{name}', name)
        except subprocess.CalledProcessError:
            continue
        if name.endswith('.zip'):
            z = zipfile.ZipFile(p)
            d = pd.read_csv(z.open([n for n in z.namelist() if n.lower().endswith('.csv')][0]), sep='|',
                            dtype={'SSUID': str, 'ssuid': str})
        else:
            d = pd.read_csv(p, sep='|', dtype={'SSUID': str, 'ssuid': str})
        d.columns = [c.upper() for c in d.columns]
        if 'PANEL' in d and 'SPANEL' not in d:
            d['SPANEL'] = d.PANEL
        if 'SPANEL' not in d:
            d['SPANEL'] = panel
        wc = [c for c in d.columns if c.startswith('FIN')]
        for c in wc:
            rows.append(pd.DataFrame({'panel': d.SPANEL.astype('int16'),
                                      'pid': d.SSUID + '_' + d.PNUM.astype('int64').astype(str),
                                      'wt_name': c, 'wt_file': name.split('.')[0].replace('_csv', ''),
                                      'first_year': np.int16(y0), 'last_year': np.int16(y1),
                                      'weight': d[c].astype('float32')}))
        os.remove(p)
    w = pd.concat(rows, ignore_index=True)
    w.to_parquet(os.path.join(DATA, 'sipp_lgtwgt_new.parquet'), index=False)
    print('longitudinal weights rows', len(w), w.groupby(['wt_file', 'wt_name', 'panel']).weight.agg(
        lambda s: (s > 0).sum()).to_string(), flush=True)
    return w


VINT = {'occ': [('0101', 'Census 2018 OCC'), ('0102', 'Census 2018 OCC'), ('0100', 'Census 2010 OCC')],
        'ind': [('1691', 'Census 2017 IND'), ('1680', 'Census 2012 IND'), ('1690', 'Census 2012 IND')]}


def combine():
    files = sorted(f for f in os.listdir(INTER) if f.startswith('sipp_py_'))
    a = pd.concat([pd.read_parquet(os.path.join(INTER, f)) for f in files], ignore_index=True)
    # code-system vintage per Census file, from signature codes present on the file
    for kind in ('occ', 'ind'):
        vint = {}
        for sf, g in a.groupby('source_file'):
            codes = set(g['main_' + kind].dropna().astype(str))
            vint[sf] = next((lab for code, lab in VINT[kind] if code in codes), 'unknown')
        a[kind + '_vintage'] = a.source_file.map(vint)
        print(kind, vint)
    a['educ4'] = educ4(a)
    a['hisp'] = hisp(a)
    w = lgtwgt() if not os.path.exists(os.path.join(DATA, 'sipp_lgtwgt_new.parquet')) else \
        pd.read_parquet(os.path.join(DATA, 'sipp_lgtwgt_new.parquet'))
    # later files repeat earlier weights (e.g. lgtwgt2014pnl4 also carries FINPNL2-3): keep one copy
    w = w.sort_values('wt_file').drop_duplicates(['panel', 'pid', 'wt_name', 'first_year', 'last_year'], keep='first')
    w.to_parquet(os.path.join(DATA, 'sipp_lgtwgt_new.parquet'), index=False)
    # longest-span longitudinal weight available for each panel (persons in sample over the whole span)
    w = w.assign(span=w.last_year - w.first_year)
    best = w.sort_values(['panel', 'span', 'last_year']).groupby('panel').tail(1)[['panel', 'wt_file', 'wt_name']]
    wb = w.merge(best, on=['panel', 'wt_file', 'wt_name'])
    wb = wb.assign(lgtwt_pnl_span=wb.first_year.astype(str) + '-' + wb.last_year.astype(str))
    a = a.merge(wb[['panel', 'pid', 'weight', 'lgtwt_pnl_span']].rename(columns={'weight': 'lgtwt_pnl'}),
                on=['panel', 'pid'], how='left')
    a['lgtwt_cy'] = np.nan  # new design: December cross-sectional weight is the calendar-year weight
    thr = pd.concat([pd.read_csv(os.path.join(INTER, f)) for f in sorted(os.listdir(INTER)) if f.startswith('topcode_')])
    thr.to_csv(os.path.join(OUT, 'topcode_thresholds_new.csv'), index=False)
    for p, g in a.groupby('panel'):
        g = g.sort_values(['pid', 'year'])
        g.to_parquet(os.path.join(DATA, f'sipp_py_new_{p}.parquet'), index=False, compression='zstd')
        print('wrote panel', p, len(g), 'years', sorted(g.year.unique()), flush=True)


if __name__ == '__main__':
    if '--combine' not in sys.argv:
        for k in SEL:
            if os.path.exists(os.path.join(INTER, f'sipp_py_{k}.parquet')) and '--force' not in sys.argv:
                print('skip', k, '(done)'); continue
            process(k)
    if '--combine' in sys.argv or not args[1:]:
        combine()
