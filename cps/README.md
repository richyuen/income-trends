# CPS ASEC: annual earnings for everyone 15+, ASEC 1988-2026 (income years 1987-2025)

Built 2026-10-10 from the public-use March supplement files: Census direct for 1998-2026, plus NBER's re-hosted copies of the Census files for 1988-1997 (Census's own datasets tree starts at 1998). No IPUMS. Raw downloads stay outside the repo (`/tmp/it_cps/raw`, about 4 GB).

## Files
| Path | What |
|---|---|
| `data/asec_<ASECYEAR>_<file>.parquet` | One row per person 15+ per file, 63 columns, nominal dollars. 42 files, about 200 MB in total. `file` is `production` except 2014 (`traditional_5x8`, `redesign_3x8`: the split-sample income questionnaire test), the 2017 research file (`research_updated`) and the 2018 bridge file (`bridge_updated`). The last two re-run ASEC 2017 and 2018 through the updated (2019+) processing system. |
| `data/asec_links.parquet` | Person matches between ASEC t and t+1 (keys `file`, `ph_seq`, `pppos` on both sides). |
| `output/validate_p38.csv` | Check against Census Table P-38, by year and file. |
| `output/link_rates.csv` | Match rates by pair of years. |
| `scripts/extract.py RAW_DIR [YEAR ...]` | Downloads anything missing and writes `data/` (`YEAR=0` prints which variables each year's dictionary lacks). |
| `scripts/validate.py`, `scripts/link.py` | Write the two outputs. |

Fixed-width positions for 1988-2018 come from NBER's per-year Stata dictionaries (`data.nber.org/data/progs/cps/cpsmarYY.dct`; 2014 uses `cpsmar2014t` and `cpsmar2014r`). They agree with the positions the retirement-trends scripts took from Census's `cpsmarYY.pdf`. 2017 research, 2018 bridge and 2019-2026 are Census CSVs (`pppub` merged to `hhpub` on `PH_SEQ = H_SEQ`). Every file passes these checks: each person matches a household; sex is 1 or 2; age is 0-90; the weighted population is plausible (241M in 1988, 339M in 2026); and PEARNVAL = WSAL_VAL + SEMP_VAL + FRSE_VAL (at most 8 exceptions in a year).

## Columns (Census names, lower case; years where a name differs are aliased to one column)
- **Keys:** `h_seq`/`ph_seq` (household within file), `pppos`, `a_lineno` (1995: PULINENO), `pf_seq`, `a_famnum`, `a_famrel`, `a_exprrp` (relationship), `h_idnum` (household ID across months: 12 characters to 1994, 15 for 1995-2004, 20 from 2005), `h_mis` (month in sample), `peridnum` (2003+), plus `asec_year`, `income_year`, `file`, `system` (legacy/updated).
- **Demographics:** `age` (top-coded at 85 or 90 depending on the year), `sex`, `race` (A_RACE to 2002, PRDTRACE from 2003, with multiple races; `race_src` names the source), `hisp` (A_REORGN to 2002, PEHSPNON from 2003; `hisp_src`), `a_maritl`, `a_hga` (education: grade attended to ASEC 1991 with `a_hgc` grade completed; degree codes 31-46 from 1992), `gestfips` (state FIPS; `hg_st60`, 1960 Census state codes, before 2005 where FIPS is missing), `h_numper`.
- **Work last year (longest job):** `workyn`, `wkswork`, `hrswk` (usual hours a week), `wewkrs`, `lkweeks`, `ljcw` (class of worker), `industry`, `occup` (detailed codes: Census 1980 codes to ASEC 2002, 2002 codes from 2003, then later revisions), `weind`, `wemind`, `poccu2`, `wemocg` (recodes).
- **Now (March):** `pemlr` (1994+), `a_wkstat`, `a_clswkr`, `a_mjind`, `a_mjocc`.
- **Earnings last year:** `pearnval` (total person earnings), `wsal_val`, `semp_val`, `frse_val`, `ern_val` (longest job), `ern_srce`, `ern_otr`, `ptotval` (total income). Allocation flags: `i_ernval`, `i_wsval`, `i_seval`, `i_frmval` (nonzero = imputed). Topcode flags: `tcernval`, `tcwsval`, `tcseval`, `tcffmval`.
- **Weights:** `marsupwt` (ASEC person weight), `a_fnlwgt` (basic CPS weight), `a_ernlwt` (earnings weight). Decimals are already applied.

## Validation: Census Table P-38 (full-time, year-round workers 15+ with earnings, by sex)
Full-time, year-round means 50 or more weeks and usually 35 or more hours. The median uses Census's own method, interpolating inside $2,500 brackets, with the MARSUPWT weight.
- **Match** in **35 of the 41 income years** P-38 covers, including both 2014 files and both versions of 2017. The counts agree within 0.05% and the medians within $50 (0.11%); in 32 of those years the medians agree within $10. (The ASEC 2017 research file has no P-38 row of its own.)
- The other years differ because the published row uses weights the public file doesn't carry. 1992: 1990-Census controls. 1999 and 2000: Census 2000-based reweights; counts are 1.1-1.5% low and medians within 0.4%. 2010: 2010-Census reweight. 2020: Census's pandemic entropy-balanced weights; the male count is 1.1% low. 2024: the September 2026 re-release of ASEC 2025 weights; the male count is 1.4% high. Medians are within 0.5% in every year.

## Linking ASEC t to t+1 (`scripts/link.py`)
This follows Madrian and Lefgren (2008): households in months 1-4 of the rotation in March of year t return in months 5-8 a year later. Pairs match on household ID (first 15 characters) and line number, and must have the same sex and race and an age change of -1 to 3.
- **Linkable:** 1988-1993 and 1996-2001 (65-76% of eligible people). 2002-2003 is 45-51%, because the eligible count includes the SCHIP expansion sample. 2004-2014 is 42-52%. 0.94 million pairs in all.
- **Not linkable:** 1993→94 (1994 redesign), 1994→95, 1995→96 (1995 sample redesign) and **every pair from 2015→16 on**. From ASEC 2015, the public household IDs are reassigned rather than followed between Marches (checked: they still match that March's basic CPS file). A probabilistic match would be needed for 2015 onward.
- People who move are not followed (the CPS samples addresses), so matched people are less mobile than the population.

## Caveats
- Series breaks: the 1994 CATI redesign; 1992 education codes; topcoding rules change (ASEC 2011+ uses rank proximity swapping, earlier years cell means); occupation and industry code systems change (2003, 2011, 2020); the 2014 income questionnaire redesign (use the two 2014 files to bridge); and 2019+ updated processing (bridge with ASEC 2017 research and 2018 bridge files). ASEC 2021-2022 weights are affected by the pandemic and its nonresponse.
- Imputed earnings are a large share in later years (whole-record imputation for supplement nonrespondents). Drop them with the `i_*` flags when estimating shock variances.
- Replicate weights (for SEs) are not downloaded here. Their locations: `CPS_ASEC_ASCII_REPWGT_YYYY.dat.gz` in each year's `march/` folder for 2005-2019, `.DAT.GZ` for 2020+, and `asec_csv_repwgt_YYYY.csv` inside the 2019+ zips. See richyuen/retirement-trends `cps/scripts/se.py`.
