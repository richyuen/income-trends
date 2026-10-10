# SIPP: person-year annual labor earnings, 1995-2024 (panels 1996, 2001, 2004, 2008, 2014, 2018-2025)

Built 2026-10-10 from Census public-use SIPP files (direct from www2.census.gov; NBER only for the 1996 layout).
Purpose: step 1 ("get the data") for estimating a labor income process (age profile + permanent/transitory shocks,
Cocco-Gomes-Maenhout style), later cut by education, industry, income group and cohort. One row per person x
calendar year, linked within panel. Dollars are **nominal** (CPI comes separately).

## Files
| File | Rows | Size | Contents |
|---|---|---|---|
| `data/sipp_py_old_1996.parquet` | 326,789 | 9.9 MB | 1996 panel, years 1995-2000 (90,671 persons) |
| `data/sipp_py_old_2001.parquet` | 246,320 | 7.5 MB | 2001 panel, years 2000-2003 (81,535 persons) |
| `data/sipp_py_old_2004.parquet` | 361,383 | 10.2 MB | 2004 panel, years 2003-2007 (104,210 persons) |
| `data/sipp_py_old_2008.parquet` | 467,864 | 12.8 MB | 2008 panel, years 2008-2013 (106,654 persons) |
| `data/sipp_py_new_2014.parquet` | 177,672 | 4.6 MB | 2014 panel, waves 1-4 = years 2013-2016 |
| `data/sipp_py_new_2018.parquet` ... `_2025.parquet` | 135,503 / 11,865 / 39,625 / 28,932 / 51,022 / 22,215 / 15,259 / 8,003 | 0.2-3.5 MB | SPANEL 2018 (yrs 2017-20), 2019 (2018 only), 2020 (2019-22), 2021 (2020-23), 2022 (2021-24), 2023 (2022-24), 2024 (2023-24), 2025 (2024) |
| `data/sipp_lgtwgt_old.parquet` | 3,256,598 | 17 MB | all Census longitudinal weights, old panels (long: panel, pid, wt_name, wt_file, first_year, last_year, weight) |
| `data/sipp_lgtwgt_new.parquet` | 583,781 | 6 MB | same for the new design (FINPNLk / FINYRk) |
| `data/new/` | | 18 MB | intermediates, one per Census file (`sipp_py_<file>.parquet`, `topcode_<file>.csv`); rebuilt by `extract_new.py` |
| `data/fred_cnp16ov.csv` | | | BLS civilian noninstitutional population 16+ (FRED CNP16OV), for the population check |

Total 1,892,452 person-years (age 15+ in the last month observed). Key: (`panel`, `pid`, `year`); `pid` = `SSUID_PNUM`
(old panels: zero-padded 12-digit SSUID + `_` + EPPPNUM), stable within panel and unique within (panel, year).
Analysis sample suggestion: `full_year` (12 months observed), `wgt_last > 0`, `imp_share == 0` (or
`imp_dollar_share` small), not `tc_any`.

## Sources (all https://www2.census.gov/programs-surveys/sipp/data/datasets/)
- **2014 panel**: `2014/wN/pu2014wN_csv.zip` + `pu2014wN_schema.json`, N = 1-4 (ref years 2013-2016). Longitudinal
  weights `2014/wN/lgtwgt2014pnlN.csv.gz` (FINPNL2-4 = waves 1-2/1-3/1-4).
- **SIPP 2018-2025**: `YYYY/puYYYY_csv.zip` + schema (ref year YYYY-1; several panels per file, SPANEL/SWAVE).
  Longitudinal weights `2019/lgtwgt2019_csv.zip` (FINYR2, panel 2018, 2017-18) and `YYYY/lgtwgtYYYYyrK_csv.zip`,
  K = 2-4 (FINYRK: persons in sample over ref years YYYY-K .. YYYY-1, by SPANEL). `2020/lgtwgt2020yr4` does not exist.
- **1996 panel**: `1996/wN/l96puwN.zip` (N=1-12). Layout: NBER `https://data.nber.org/sipp/1996/sip96l1.dct`
  (Census now serves re-edited longitudinal files whose layout is NOT the posted `sip96wNd.asc`). Weights `1996/ctl_fer.zip`
  (dict `1996/ctl_ferd.asc`): LGTPNLWT, LGTCY1-4WT (= 1996-1999).
- **2001 panel**: `2001/wN/l01puwN.zip` (N=1-9), dict `2001/w1/l01puw1d.txt`; weights `2001/w9/lgtwgt2001w9.zip`
  (dict `2001/lgtwt01d.txt`): LGTPNWT1-3, LGTCY1-3WT (= 2001-2003).
- **2004 panel**: `2004/wN/l04puwN.zip` (N=1-12), dict `2004/w1/l04puw1d.txt`; weights `2004/w12/lgtwgt2004w12.zip`
  (dict `2004/w12/lgt04w12d.txt`): LGTPNWT1-4, LGTCY1-4WT (= 2004-2007).
- **2008 panel**: `2008/wN/l08puwN.zip` (N=1-16), dict `2008/w1/l08puw1d.txt.old2`; weights `2008/w16/lgtwgt2008w16.zip`
  (dict `2008/w16/lgtwgt2008w16.txt`): LGTPN1-5WT, LGTCY1-5WT (= 2009-2013).
- New-design data dictionary used for codes: `programs-surveys/sipp/tech-documentation/data-dictionaries/2023/2023_SIPP_Data_Dictionary.pdf`.
- Old-panel layouts were checked on every wave (`extract_old.checks`): SWAVE/SPANEL/person-number/month ranges, ages
  15-90 for >99.7% of adults, and TPEARN = TPMSUM1+TPMSUM2+TBMSUM1+TBMSUM2+TMLMSUM (or a business present) for >99.9%.

**Replicate weights (not downloaded):** new design `YYYY/rwYYYY_csv.zip` (240 Fay BRR, monthly; use MONTHCODE 12) and
longitudinal `YYYY/lgtrwYYYYyrK_csv.zip`; 2014 panel `2014/wN/rw14wN.csv.gz` and `2014/wN/lrw2014pnlN.csv.gz`;
1996 `1996/wN/rw96wN.zip` (core, dict `1996/rw96wxd.txt`) and `1996/w1-4/lrw96cyN.zip`, `1996/lrw96pnl.zip`;
2001 `2001/wN/rw01wN.zip` (dict `2001/rw01wxd.txt`), longitudinal in `lrw01_xx` layout; 2004 `2004/wN/rw04wN.zip`,
`2004/w4/lrw04_cyN.zip`, `lrw04_pnlN.zip`; 2008 `2008/wN/rw08wN.zip`, `2008/w8/lrw08cyN.zip`, `lrw08pnN.zip`.
Old panels use 108 (1996/2001) or 120 (2004/2008) replicates, Fay factor 4/R; new design 240.

## Definitions (columns)
- `panel`, `design` (old/new), `pid`, `year` (calendar = reference year), `source_file`; `swave` (new: wave of the
  panel in that file) or `wave_first`/`wave_last` (old: core waves contributing to the year).
- `months_obs` months with a person record in the year (new design: excluding months with RIN_UNIV=2, outside the
  survey frame, e.g. institutionalized/abroad); `first_month`, `last_month`, `full_year` (= 12 months).
- **Earnings** (sums of monthly values over observed months):
  - `earn_tot` = sum of monthly **TPEARN** (both designs: total person earnings = all jobs + business income incl.
    profit/loss, after topcoding).
  - `earn_wage` wage and salary: new = TJBn_MSUM of jobs with EJBn_JBORSE=1 (employer); old = TPMSUM1+TPMSUM2.
  - `earn_se` self-employment: new = TPEARN minus wage and other (i.e. TJBn_MSUM of business jobs plus the business
    profit/loss that TPEARN spreads over months); old = TBMSUM1+TBMSUM2 plus the TPEARN residual when the person has a
    business that month (2004/2008 TPEARN adds unincorporated profit TPRFTB).
  - `earn_oth` new: jobs with JBORSE=3 ("other work arrangement"); old: TMLMSUM (moonlighting/extra work). Any TPEARN
    residual with no business goes here. Always `earn_wage + earn_se + earn_oth == earn_tot`.
  - `months_earn` months with TPEARN > 0; `months_earn_nz` months with TPEARN != 0.
- `months_emp` months with RMESR 1-5 (with a job at least part of the month); `weeks_job` sum of RMWKWJB (weeks with
  a job, incl. paid absence; both designs); `hrs_all_avg` mean TMWKHRS (avg weekly hours, all jobs) over months with a
  job, **new design only**.
- **Main job** = job with the largest annual earnings in the year (ties: more months). New design: job line n=1..7
  (`main_jobkey`=n, `main_jobid`=EJBn_JOBID, consistent across waves). Old: employer EENO (`main_jobkey`=EENO) or
  business EBNO (`main_jobkey`=100+EBNO), persistent within panel. `main_earn`, `main_months`,
  `main_ind`/`main_occ` raw codes (strings), `main_cls` class of worker (new EJBn_CLWRK 1 federal, 2 military, 3 state,
  4 local, 5 private for-profit, 6 nonprofit, 7 SE incorporated, 8 SE unincorporated; old ECLWRKk 1 private for-profit,
  2 nonprofit, 3 local, 4 state, 5 federal, 6 unpaid family; NaN for businesses), `main_se` (new JBORSE=2; old =
  business), `main_hrs` usual hours/week (new TJBn_JOBHRS1 = first hours spell; old EJBHRSk / EHRSBSk), `n_jobs`.
  Attributes are from the last month of that job with a non-missing value.
- `ind_vintage`/`occ_vintage`: 1996, 2001 = Census 1990 IND/OCC (3-digit); 2004, 2008 = Census 2002 IND / 2000 OCC
  (4-digit; old-panel **business** industry `TBSIND` is a 2-digit recode); 2014 panel = Census 2012 IND / 2010 OCC;
  SIPP 2018-2025 = Census 2017 IND / 2018 OCC (new-design vintages detected from signature codes, see `extract_new.VINT`).
- Demographics at the last observed month: `age` (new TAGE_EHC monthly age; old TAGE; topcoded at 90 / 85),
  `byear` (TDOB_BYEAR / TBYEAR), `sex` (1 m, 2 f), `race` (ERACE; 1996/2001: 1 white 2 black 3 AIAN 4 API; 2004+:
  1 white alone 2 black alone 3 asian alone 4 residual), `origin` raw EORIGIN, `hisp` (1996/2001 codes 20-28; else 1),
  `educ` raw (new EEDUC 31-46; old EEDUCATE 31-47; coding differs), `educ4` (1 <HS, 2 HS/GED, 3 some college/assoc/
  vocational, 4 BA+), `ms` (EMS), `state` (FIPS; new TEHC_ST monthly, else TST_INTV; old TFIPSST), `hhsize`
  (RHNUMPER / EHHNUMPP), `famsize` (new: persons with the same SSUID, ERESIDENCEID, RFAMNUM in the month; old EFNP),
  `relrp` (ERELRPE / ERRP; codes differ).
- **Weights**: `wgt_last` = WPFINWGT of the last observed month, `wgt_month` = that month (12 for December). For the
  new design the December WPFINWGT is the calendar-year cross-sectional weight. Old panels: `lgtwt_cy` Census
  calendar-year longitudinal weight for that year (LGTCYkWT), `lgtwt_pnl` final panel weight (1996 LGTPNLWT, 2001
  LGTPNWT3, 2004 LGTPNWT4, 2008 LGTPN5WT). New: `lgtwt_pnl` = longest-span FIN* weight for the panel
  (`lgtwt_pnl_span` gives the years), `lgtwt_cy` NaN. All other longitudinal weights are in `sipp_lgtwgt_*.parquet`.
  Fixed-width weights have 4 implied decimals (divided by 10^4).
- **Imputation**: a month counts as imputed when it has nonzero earnings and (a) any earnings component of a job
  earning that month is imputed or (b) the person is a Type-Z (whole-person imputation: new EINTTYPE=3; old EPPINTVW
  3-4). New: status flags of the pay inputs TJBn_{ANNSAL,HOURLY,WKLY,BWKLY,MTHLY,SMTHLY,OTHER}1-3, GAMT1, PRFTB in
  {2 hot deck, 4 model, 5 cold deck, 6 range, 7, 8 combinations} (3 logical not counted; APEARN/AJBn_MSUM are 9 =
  "derived" and uninformative). Old: APMSUMk, ABMSUMk, AMLMSUM in {1 hot deck, 2 cold deck, 4 prior-wave} (3 logical
  not counted). Columns: `imp_months`, `imp_share` (= imp_months / months_earn_nz), `imp_dollar_share` (imputed |$| /
  total |$|), `typez_months`.
- **Topcodes** (not flagged by Census; heuristic): Census replaces values above the cap with cell means, which show up
  as heaps at the top. Old panels: the most frequent value at or above the 99.9th percentile of monthly TPMSUM / TBMSUM
  / TMLMSUM (>=5 persons); the lowest of the three is applied to all components (1996 $29,660/month, 2001 $29,057, 2004
  $37,750, 2008 $31,900). New design: per file and pay-input type, walk down the distinct values from the top while each
  is shared by >=5 jobs and is above the 99th percentile (`output/topcode_thresholds_new.csv`). `tc_months` / `tc_any`
  = months / any month with a component at or above the threshold.

## Validation (`output/`)
Files: `validation_panel_year.csv` (also weighted medians by sex, Type-Z, topcode and SE shares, imputed dollar
share), `linkage_panel_year.csv`, `population_check.csv`, `seam_old_panels.csv`, `topcode_thresholds_{old,new}.csv`.

(a)+(b) 12-month earners aged 25-64 with positive annual earnings, `wgt_last` weights, nominal $. "linked t+1": share
of all person-year records with a record for the same person in t+1 (same panel) / share of these earners with a
12-month record in t+1 (0 in each panel's last year by construction).

| panel | year | persons 15+ | 12-mo | 12-mo earners 25-64 (n / wtd M) | mean | median | mean men / women | imputed any | linked t+1 (all / earners 12m) |
|---|---|---|---|---|---|---|---|---|---|
| 1996 | 1996 | 77,091 | 30,725 | 16,985 / 54.1 | 29,152 | 22,971 | 36,255 / 21,290 | 0.30 | 0.88 / 0.83 |
| 1996 | 1997 | 72,920 | 55,118 | 30,455 / 106.8 | 29,883 | 23,780 | 36,768 / 22,267 | 0.34 | 0.85 / 0.86 |
| 1996 | 1998 | 66,876 | 51,989 | 28,486 / 106.5 | 31,343 | 24,900 | 38,442 / 23,498 | 0.34 | 0.89 / 0.68 |
| 1996 | 1999 | 62,963 | 38,999 | 21,420 / 81.9 | 32,651 | 25,736 | 39,906 / 24,687 | 0.34 | 0.45 / 0.00 |
| 2001 | 2001 | 73,757 | 48,753 | 27,253 / 113.4 | 34,656 | 27,016 | 42,355 / 26,155 | 0.38 | 0.78 / 0.85 |
| 2001 | 2002 | 61,829 | 46,052 | 25,063 / 108.5 | 35,690 | 27,804 | 43,156 / 27,428 | 0.38 | 0.89 / 0.22 |
| 2001 | 2003 | 58,635 | 11,660 | 6,239 / 28.1 | 37,352 | 29,039 | 44,760 / 28,991 | 0.36 | 0.00 / 0.00 |
| 2004 | 2004 | 91,651 | 68,525 | 37,622 / 115.9 | 38,848 | 29,808 | 46,993 / 29,784 | 0.23 | 0.88 / 0.82 |
| 2004 | 2005 | 87,277 | 62,229 | 33,466 / 110.4 | 39,772 | 30,310 | 48,135 / 30,473 | 0.21 | 0.87 / 0.39 |
| 2004 | 2006 | 81,103 | 28,115 | 14,746 / 110.4 | 41,476 | 31,104 | 50,480 / 31,413 | 0.21 | 0.42 / 0.21 |
| 2004 | 2007 | 36,902 | 6,929 | 3,532 / 27.8 | 42,888 | 32,136 | 50,488 / 34,287 | 0.21 | 0.00 / 0.00 |
| 2008 | 2009 | 86,774 | 60,807 | 31,425 / 109.6 | 42,767 | 32,136 | 50,181 / 34,619 | 0.21 | 0.88 / 0.80 |
| 2008 | 2010 | 82,269 | 56,424 | 28,116 / 106.6 | 42,777 | 32,004 | 49,848 / 34,876 | 0.23 | 0.86 / 0.81 |
| 2008 | 2011 | 76,949 | 53,165 | 25,903 / 106.0 | 43,505 | 32,392 | 50,619 / 35,593 | 0.24 | 0.87 / 0.82 |
| 2008 | 2012 | 73,539 | 50,102 | 24,091 / 104.3 | 44,373 | 33,180 | 51,660 / 36,254 | 0.24 | 0.84 / 0.00 |
| 2014 | 2013 | 58,000 | 58,000 | 27,126 / 123.4 | 53,724 | 38,103 | 64,279 / 42,011 | 0.23 | 0.74 / 0.71 |
| 2014 | 2014 | 46,285 | 44,857 | 20,896 / 126.8 | 53,570 | 37,603 | 63,930 / 42,059 | 0.25 | 0.72 / 0.70 |
| 2014 | 2015 | 38,827 | 37,010 | 16,965 / 128.6 | 54,934 | 39,912 | 65,719 / 43,189 | 0.23 | 0.71 / 0.71 |
| 2014 | 2016 | 34,560 | 32,868 | 14,958 / 131.0 | 57,312 | 40,224 | 68,034 / 45,636 | 0.23 | 0.00 / 0.00 |
| 2018 | 2017 | 51,801 | 51,438 | 24,294 / 128.0 | 64,071 | 43,118 | 76,262 / 50,689 | 0.24 | 0.54 / 0.50 |
| 2018 | 2018 | 29,769 | 28,792 | 12,969 / 82.8 | 63,083 | 42,586 | 74,084 / 50,567 | 0.25 | 0.64 / 0.63 |
| 2018 | 2019 | 28,235 | 27,310 | 12,105 / 85.1 | 68,216 | 45,883 | 81,347 / 53,837 | 0.22 | 0.65 / 0.64 |
| 2018 | 2020 | 25,698 | 24,714 | 10,688 / 68.2 | 68,116 | 46,356 | 78,848 / 56,207 | 0.23 | 0.00 / 0.00 |
| 2019 | 2018 | 11,865 | 11,785 | 5,075 / 45.7 | 61,925 | 42,633 | 72,298 / 50,453 | 0.20 | 0.00 / 0.00 |
| 2020 | 2019 | 15,812 | 15,728 | 7,074 / 45.4 | 67,906 | 46,457 | 80,348 / 54,299 | 0.23 | 0.60 / 0.57 |
| 2020 | 2020 | 10,082 | 9,779 | 4,218 / 34.0 | 64,272 | 45,000 | 75,625 / 52,196 | 0.24 | 0.62 / 0.59 |
| 2020 | 2021 | 7,668 | 7,395 | 2,999 / 35.0 | 73,919 | 51,136 | 87,621 / 58,878 | 0.23 | 0.69 / 0.69 |
| 2020 | 2022 | 6,063 | 5,875 | 2,348 / 31.0 | 79,840 | 54,195 | 94,206 / 63,789 | 0.21 | 0.00 / 0.00 |
| 2021 | 2020 | 12,045 | 12,010 | 5,481 / 26.9 | 70,207 | 47,788 | 81,540 / 58,030 | 0.26 | 0.52 / 0.49 |
| 2021 | 2021 | 6,637 | 6,423 | 2,869 / 27.4 | 71,849 | 49,533 | 82,748 / 59,570 | 0.24 | 0.65 / 0.65 |
| 2021 | 2022 | 5,391 | 5,246 | 2,288 / 23.4 | 82,107 | 56,305 | 94,454 / 68,687 | 0.22 | 0.70 / 0.71 |
| 2021 | 2023 | 4,859 | 4,715 | 2,066 / 25.4 | 84,062 | 57,047 | 94,939 / 72,712 | 0.22 | 0.00 / 0.00 |
| 2022 | 2021 | 20,085 | 19,987 | 8,780 / 65.6 | 74,722 | 50,099 | 86,860 / 61,386 | 0.26 | 0.56 / 0.53 |
| 2022 | 2022 | 11,949 | 11,591 | 4,885 / 53.1 | 77,549 | 53,482 | 89,140 / 65,144 | 0.23 | 0.66 / 0.66 |
| 2022 | 2023 | 10,135 | 9,831 | 4,206 / 58.0 | 84,229 | 57,281 | 93,281 / 73,858 | 0.25 | 0.68 / 0.66 |
| 2022 | 2024 | 8,853 | 8,552 | 3,488 / 58.7 | 82,272 | 59,939 | 95,978 / 67,987 | 0.24 | 0.00 / 0.00 |
| 2023 | 2022 | 10,700 | 10,630 | 4,771 / 25.0 | 76,027 | 52,000 | 90,189 / 60,441 | 0.26 | 0.57 / 0.54 |
| 2023 | 2023 | 6,485 | 6,294 | 2,726 / 24.8 | 81,951 | 57,155 | 96,692 / 64,903 | 0.25 | 0.62 / 0.62 |
| 2023 | 2024 | 5,030 | 4,882 | 2,059 / 24.8 | 79,907 | 56,160 | 90,298 / 68,012 | 0.24 | 0.00 / 0.00 |
| 2024 | 2023 | 9,799 | 9,723 | 4,306 / 25.4 | 81,140 | 55,151 | 95,081 / 66,302 | 0.26 | 0.53 / 0.49 |
| 2024 | 2024 | 5,460 | 5,302 | 2,246 / 24.3 | 83,505 | 54,542 | 98,935 / 66,061 | 0.26 | 0.00 / 0.00 |
| 2025 | 2024 | 8,003 | 7,973 | 3,452 / 25.1 | 83,648 | 59,826 | 94,018 / 72,322 | 0.26 | 0.00 / 0.00 |

(c) **Population check** (`population_check.csv`): December-weighted persons 16+ vs BLS civilian noninstitutional
population 16+ (FRED CNP16OV, December). Ratio 1.000-1.004 in every year a panel (old) or a Census file (new, summing
its panels) covers December for all rotation groups (1996-98, 2001-02, 2004-06, 2008-12, 2013-2024; e.g. 2022: 264.9M
vs 264.8M). Ratios of 0.25 / 0.75 in 1995, 1999, 2000, 2003, 2007 are panel start/end years in which only 1 or 3 of
the 4 rotation groups are in sample in December (expected, not an error); 2013 (2008 panel) has no December.
Old-panel calendar-year longitudinal weights (`lgtwt_cy`) are positive for 95-100% of full-year persons.

Things that look odd (all explained above or in caveats): the 2012->2013 level jump (design break); low full-year
shares at panel ends and in 2006 (2004-panel sample cut); new-design linkage of only 50-57% from a panel's first year;
Type-Z (fully imputed) persons rising from 6% (2014 w1) to 14-16% (SIPP 2021+); topcode-flag shares 0.4-1.8% (old)
vs 2-3% (new, pay-rate topcodes are lower relative to the distribution and the heuristic is broader).

## Caveats
1. **Design break 2013 vs 2012.** Old panels (1996-2008) are 4-month-recall interviews; 2014+ is an annual interview
   with an event-history calendar. Mean earnings of 12-month earners 25-64 jump from $44.4k (2008 panel, 2012) to
   $53.7k (2014 panel, 2013), medians $33.2k -> $38.1k: about +20%, far more than one year of wage growth. Different
   imputation (old 10-25% of dollars vs new 20-28%), topcodes and earnings questions (pay-rate based in 2014+). Treat
   eras separately (panel fixed effects / era dummies) and do not splice levels.
2. **Seam effect (old panels)** `seam_old_panels.csv`: month-to-month changes in TPEARN are 2-3x as common across wave
   seams as within waves (1996: 89% vs 47% of pairs; 2008: 50% vs 16%); job starts/stops 2.5x. Within-wave months are
   often constant (recall/imputation smoothing). Annual sums are less affected, but transitory variances estimated from
   sub-annual data would be. 2014+: one interview per year, so the seam is between calendar years (Dec->Jan), which is
   exactly the annual-change margin used for income-process estimation; be aware it can inflate year-to-year changes.
3. **Partial years and panel start/end** (rotation groups): 1996 panel 1996 only ~40% full-year (rotations 1-2), 1999
   62%; 1995 and 2000 have no full years. 2001 panel: 2000 none, 2003 20%. 2004 panel: 2003 none, 2006 35% (the **wave
   9 sample cut** of ~55% in mid-2006), 2007 19%. 2008 panel: 2008 and 2013 none (panel ends Nov 2013). New design: all
   files give nearly 12 months (2014 w1: 100%; later 95-99%); persons who leave mid-year keep their partial months.
4. **Overlapping panels**: new-design files hold 2-4 panels in the same year (each panel's weights are a share of the
   file total; the file total is the population). Old panels overlap in 2000 (1996/2001), 2003 (2001/2004) only in
   partial years. Use panel x year cells or reweight when pooling.
5. **Attrition / linkage** (`linkage_panel_year.csv`): old panels 84-89% of person-year records have a next-year record
   (12-month earners 25-64 with a 12-month next year: 80-86% in full-coverage years). 2014 panel 71-74%. SIPP 2018+
   only 52-70% (wave-1 attrition highest: 49-57% of 12-month earners link to a 12-month next year). The 2019 panel has
   only one wave (ref year 2018); the 2024 and 2025 panels end in 2024 until SIPP 2026 is released.
6. **Sample sizes** in new design are small per panel-year (2-9k 12-month earners 25-64 per panel; ~12-25k per file).
7. **Imputation** is heavy: 20-38% of 12-month earners 25-64 have at least one imputed month; Type-Z persons 5-8%
   (old) and 6-16% (new); imputed dollars 10-25% (old) and 20-28% (new) of earnings. Drop or flag in shock estimation (imputed values are hot-deck draws, which add spurious
   transitory variance and break autocorrelation).
8. **Codes**: industry/occupation vintages differ (see above); crosswalk before cutting by industry across eras.
   Education coding differs between designs (`educ4` harmonizes). Old-panel race categories change in 2004.
9. 2014 panel lacks RIN_UNIV (all months counted). Age is topcoded: 90 in the new design; old panels topcode TAGE at
   about 85 at entry (yearly maxima 83-89 as people age in the panel).
12. If a run of `extract_new.py` dies with an exception, the pyarrow CSV reader thread can keep the process alive
   (sleeping); kill it before rerunning.
10. Old-panel monthly earnings are recorded per job in 4-month waves; `weeks_job`, `months_emp` come from monthly
   recodes and are comparable across designs; `hrs_all_avg` is new-design only.
11. 1990-1993 panels are available but not built: Census `datasets/1990/` ... `1993/` (core waves in `wN/`, full-panel
   longitudinal files `s90lgt8w.zip`, `s91lgt8w.zip`, `s92lgt10w.zip`, `s93l9w.zip` with dictionaries `s90l8wdd.asc`
   etc., and revised job-ID files); NBER `data.nber.org/sipp/1990/` has Stata dictionaries. The longitudinal files
   carry monthly earnings for the whole panel in one record per person, so adding them would be cheap.

## How to rerun
```
python3 -I sipp/scripts/extract_old.py /tmp/it_sipp/raw            # ~25 min, ~1.5 GB downloads; peak RAM ~3 GB
python3 -I sipp/scripts/extract_new.py /tmp/it_sipp/raw            # ~15 min, ~1.6 GB downloads; peak RAM ~2 GB
python3 -I sipp/scripts/validate.py /tmp/it_sipp/cache_old          # ~1 min
```
`extract_old.py [RAW_DIR] [PANELS]` caches each wave's needed columns to `RAW_DIR/../cache_old/` (220 MB) and deletes
the zip. `extract_new.py [RAW_DIR] [FILES] [--force] [--combine]` (FILES like `2014w1 2018 2025`) writes per-file
intermediates to `data/new/`, skips files already done unless `--force`, and `--combine` (or a run without FILES)
assembles the per-panel files and longitudinal weights. Scripts: `layouts.py` (dictionary parsers), `annual.py`
(month -> year collapse, main job, topcode heuristics, educ4/hisp).
