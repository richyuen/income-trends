# PSID family-year panel, 1968-2023 (survey years; income years 1967-2022)

Built 2026-10-10 from two PSID Data Center extracts ("All Individuals Data", 85,536 individuals, one row per person, with each wave's family-file variables attached through that wave's interview number). It is the PSID input for the labor income process (deterministic age profile plus permanent and transitory shocks) and replicates the sample of Cocco, Gomes and Maenhout (2005, RFS, Appendix B). The plan is to extend it later by education, industry, income group and cohort.

**PSID conditions of use:** raw PSID files and person-level derived data never go into this repo. The repo holds only code, the variable map (names, labels and codebook value codes) and aggregate tables. The panels are written to `/mnt/project-files/psid/`, the private project folder.

## Inputs (not in the repo)
| Job | Contents | Where it was unzipped |
|---|---|---|
| J366057 | Main extract, 1,625 variables: IDs, the individual-file items (interview number, sequence, relationship, age, education, employment status), and per wave head/wife age, sex, marital status, education, FU size, children, hours, labor income, wages, taxable income, family income, unemployment and workers' comp, Social Security, employment status, occupation, industry, family weight | `/tmp/it_psid/raw2/` |
| J366052 | First extract, 703 variables: state, transfers (SSI, other welfare, child support, help from relatives) for head and wife, year of birth (1988+), family weights | `/tmp/it_psid/raw/` |

The two files have the same 85,536 rows in the same order (checked on ER30001 and ER30002). **Neither extract has individual (cross-sectional or longitudinal) weights**, and J366052's 1968-2001 "occupation" items are not in this version of the file. Occupation therefore comes from J366057.

## Files
| Path | What |
|---|---|
| `scripts/varmap.py` | The hand-checked variable map (explicit `MAP` table) → `varmap.csv`. Reads only the `.do` labels and the codebook text. |
| `varmap.csv` | One row per survey year × concept (1,821 rows, 87 concepts). A concept has no row in a year with no variable. Columns: `var`, `job`, `label`, `na_codes` (missing-data codes set to NaN), `top_code`/`bottom_code` (copied from the codebook), `note`. |
| `scripts/build.py RAW_DIR1 RAW_DIR2 [OUT_DIR]` | Reads both fixed-width files with the infix positions in the `.do` files, applies `varmap.csv`, and writes the two panels. Takes about 80 seconds and 3 GB of RAM. |
| `scripts/validate.py [PANEL_DIR]` | Writes the aggregate checks in `output/`. |
| `output/validation_by_year.csv` | By survey year and group (all, SRC+SEO core, SRC): number of heads, weights, weighted and unweighted mean and median head labor income, share with positive labor income, mean age, share married, share male, mean CGM income, and the modal positive labor income value with its share. |
| `output/cps_compare.csv` | Male heads aged 25-60 (PSID) vs male householders aged 25-60 (CPS ASEC `pearnval`, `marsupwt`): mean, median, share with earnings, mean if positive. |
| `output/jumps.csv` | Year-to-year changes, flagged. |
| `output/cgm_components.csv` | The components of `cgm_inc` in each year, what is missing, and the mean of each component. |
| `output/cgm_sample_check.csv` | Our CGM-style estimation sample against CGM's Table 1. |
| `output/sentinel_counts.csv` | Heads with a missing-data code or a top/bottom code, by year and concept. |
| `/mnt/project-files/psid/psid_family_year.parquet` | 320,456 family-years (one per family and wave, for the head), 108 columns, 15.7 MB. |
| `/mnt/project-files/psid/psid_person_year.parquet` | 910,869 person-years (everyone in a responding FU in each wave), 17 columns, 5.7 MB. |

## Variable map: what was wrong in the first-pass (regex) map
The regex map (`varmap.py` before 2026-10-10) mis-assigned or missed these. All are fixed in the explicit table.
- **Wife labor income** was found only for 1968-1975 and 1993+. From 1976 to 1992 it is labelled `WIFES ANNUAL WAGE`, `WIFE 1976 WAGES` or `WIFE 19xx LABOR/WAGE`, but the codebook defines it as her labor income (V4379, V5289, V5788, V6398 ... V20436). In 1993 the right variable is V23324 (total labor income), not V21807 (excluding business and farm income).
- **Head labor income:** 1976 is V5031 (`HEAD TOTAL LABOR Y`). 1997 and 1999 are ER12080 and ER16463 (`LABOR INCOME-HEAD`).
- **Head wages:** 1968-1969 exist only in brackets (V251, V699; now `wages_h_bkt`). 1976 is V4373 (`ANNUAL WAGES`).
- **Unemployment and workers' comp:** 1970-1976 is one combined head item (V1214 ... V4397; the 1973 label says H+W, but the codebook says head). 1977-1993 head items are separate. Wife items exist only for 1985-1993 and 2005+. From 2005 the map now uses the generated annual amounts (`HEAD UNEMPLOYMENT COMPENSATION-2004` and so on), not the as-reported `AMT` items.
- **Social Security:** 1970 (V1212) is the head only, not head+wife. Head+wife is combined 1971-1985. Head and wife are separate 1986-1993 and 2005+. Only the family total is available 1994-2003.
- **Education:** heads have years of schooling in 1975-1984 and 1991+ and only bracket codes in 1968-1974 and 1985-1990 (the regex skipped the `BKT` versions and mixed the two types). Wife education is a bracket only in 1968 and 1972-1974, is asked only of new wives in 1973, and is missing in 1969-1971.
- **Marital status:** the reported (legal) status and the generated status (married or cohabiting, spouse present, 1977+) are now separate concepts.
- **Employment status:** 1994+ uses the first mention (ER2069 ...). The regex took the single 1994-1996 item for some years and nothing for 1997+. Wife status is not in the extract for 1968-1975 and 1977-1978.
- **Occupation and industry:** 1968-1980 use the retrospective 3-digit 1970 Census codes (`_A`/`_B`; these were coded only for selected heads). The original PSID 1-digit and 2-digit codes are in `occ_h_orig`/`indus_h_orig`, and 1974 V3529 is already 3-digit. 1981-2001 are 1970 3-digit codes, 2003-2015 2000 codes, and 2017+ 2010 occupation and 2012 industry codes (4 digits).
- **Family weights:** picked by year (core 1968-1992; revised core longitudinal 1993-1996; core/immigrant 1997-2023). The regex sometimes matched other variables.
- **Transfers (J366052):** SSI, other welfare, child support and help from relatives, mapped by scope: head only, head+wife combined, or head and wife separately (see the next section). Child support is head+wife in 1976-1980 and includes alimony in 1970-1976. Help from relatives is bracketed in 1968-1975.

## Definitions (family-year file)
- One row per family and wave, for the **head** (reference person from 2017): sequence number 1 and relationship 1 (to 1982) or 10 (1983+); in 1968 relationship 1. The **spouse** is the FU member with relationship 2, 20 or 22 and sequence 1-20. The 1968-1982 code 9 ("husband of head") and the 1983+ code 90 are not treated as spouses. Every wave has exactly one head per responding family. `married` = `spouse_present`.
- `year` is the survey year and `income_year` = year - 1. All amounts are nominal.
- **Sample** (from the head's ER30001): SRC < 3000, SEO 5001-6872, IMM9799 3001-3511, IMM1719 4001-4851, LATINO 7001-9308.
- **Weights:** `fam_weight` with `weight_series`. Latino families have weight 0 in the core weights (1990-1995). 2017 has 452 zero-weight families.
- **Education:** `educ_yrs_h` (0-17) takes the family-file years first, then the individual-file years for the head that wave (1968 and 1979+), then the bracket mapped to years (0-1→4, 2→7, 3→10, 4-5→12, 6→14, 7→16, 8→17). The source is in `educ_src_h`. Groups: `educ4_h` (<12, 12, 13-15, 16+) and `educ3_h`, CGM's groups (<12, 12-15, 16+). `educ_yrs_h_p` is a person-level value: the mode of the head's wave values at age 25+ (ties go to the higher value). It is useful because 2003-2007 have about 450 heads a year with education NA. The same fields exist for the spouse (`_sp`). Checks: in 1984 the family-file and individual-file years agree for 100% of heads, and in other years for 94-96%. Bracket codes line up with years (bracket 3 has a mean of 10.2 years and bracket 6 a mean of 13.9).
- **Employment status:** `emp_h` (raw), `emp_h8` (1976+ codes; in 1968-1975 code 4 = retired *or disabled*, `emp_scheme` says so), and `emp_h3` (working or temporarily laid off / unemployed / out of the labor force).
- **Occupation and industry:** `occ_h`, `indus_h` and `occ_w` with vintages `occ_vint`/`indus_vint`, and `occ_h_orig`/`indus_h_orig` with `occ_orig_vint`/`indus_orig_vint`. 0 (inapplicable) is set to NaN. 1968-1980 retrospective codes exist only for selected heads (about 70% have one).
- **Birth year:** `yob_h` is the modal reported year of birth (1988+ waves) or, failing that, survey year minus age (`yob_src_h`).
- **CGM labor income `cgm_inc`:** head + spouse labor income + unemployment + workers' comp + Social Security + SSI + other welfare + child support + help from relatives, using what each year has (`cgm_components`; gaps in `cgm_missing`; full table in `output/cgm_components.csv`):
  - 1968-1969: labor income + help from relatives (bracket midpoints) only.
  - 1970: head-only UC/WC, SS, welfare and child support.
  - 1971-1984: SS, SSI (from 1975) and welfare are head+wife; UC/WC and help are the head's.
  - 1985-1993 and 2005-2023: every component for head and wife.
  - **1994-2003: only labor income plus family Social Security.** UC, WC, SSI, welfare, child support and help exist only as as-reported amounts per time unit (`*_rep`, kept out of every total; the time-unit variables are not in the extracts).
  - **From 1994, PSID labor income excludes farm income and the labor part of business income** (codebook text of ER4140 etc.). Before 1994 both were included.

## Missing-data codes and top codes
- Codes are copied from the codebook value tables into `varmap.csv`: NA, DK, refused, "Wild code", and "Latino/Immigrant sample family" are set to NaN. Every set value is listed in the row's `na_flags` (concept names). Top and bottom codes are kept as values and flagged in `tc_flags`.
- Generated income amounts carry no NA codes ("all missing data were assigned", i.e. imputed by PSID). The exceptions are the Latino families in 1994-1995 (labor and family income, hours, taxable income all 9,999,999 → NaN; 2,106 and 1,834 heads) and the 1997 immigrant families' wages (441).
- **Top codes:** labor income and wages $99,999 (1970-1982 surveys), $999,999 (1983-1992), $9,999,999 after that. Only a handful of heads per year are top-coded (at most 16, in 1982). Family and taxable income had $99,999 top codes through the 1978-1979 surveys (at most 16 heads a year). Taxable income has bottom codes: -$9,999 in 1975-1978, hit by 9 heads in all; -$999,999 later, never hit. Transfers had $9,999 top codes in some 1970s years (rare).
- Bracket-only items: head wages 1968-1969 (`wages_h_bkt`), help from relatives 1968-1975 (`help_h_bkt`, midpoint in `help_h_bktmid`; code 8 = $10,000+ is set to 10,000), and the education brackets. Family income in 1972-1993 codes "$1 or less, including zero and negative" as 1.

## Validation highlights
- **Family counts** match PSID's published counts: 4,802 in 1968 (2,930 SRC + 1,872 SEO), 4,460 in 1969, 7,114 in 1989, 9,371 in 1990 (Latino added), 9,977 in 1993, 10,764 in 1994, 8,511 in 1996 (Latino dropped), 6,747 in 1997 (SEO cut, immigrant refresher added), 9,607 in 2017, and 9,152 in 2023.
- **CGM replication** (`output/cgm_sample_check.csv`): SRC male heads aged 20-65, surveys 1970-1992, excluding retired, housewives and students, positive `cgm_inc`, with a new unit when the education group changes. We get 1,139 / 2,919 / 1,134 units with T-bar 8.47 / 9.61 / 11.27 (no HS / HS / college). CGM report 1,104 / 2,816 / 1,110 and 8.58 / 9.57 / 11.06. Our share of zero-income observations dropped is 0.33% (CGM: 0.495%).
- **CPS check** (`output/cps_compare.csv`), male heads/householders aged 25-60, nominal means:
  - PSID/CPS mean ratio: 1.08-1.13 for income years 1987-1994, 0.96-1.04 for 1995-2003, 1.07-1.13 for 2004-2012, and 0.99-1.04 for 2014-2022.
  - Medians are within ±8% in all years (0.94-1.08).
  - Reasons the levels differ: the PSID head is always the husband in a couple, while the CPS householder can be the wife; and CPS raised its earnings top code in ASEC 1996, so CPS jumps +12% in income year 1995.
  - The share with positive earnings is 94-95% in PSID vs 93-94% in CPS for surveys 1988-1992 (93% in both in 1993), but 87-90% vs 90-93% for surveys 1994-2003. That gap is the 1994 change in the definition of labor income (business and farm labor income dropped).
- **Flagged jumps** (`output/jumps.csv`):
  - 1990 (+28% heads, Latino sample; mean age +1.2).
  - **1993→1994** (processing change; zero labor income among male heads 25-60 rises from 8.0% to 13.0% because self-employed heads lose business labor income).
  - 1996 (Latino dropped; CPS top-code change).
  - 1997 (SEO cut by about half, immigrant sample added).
  - The biennial switch after 1997 is visible only as two-year gaps.
- **Imputation mass points:** the modal positive head labor income holds 5.8% of positive values in 1997 ($26,000), 6.2% in 1999 ($29,000), 5.2% in 2003 and 4.3% in 2005, against about 2% in other years. These look like assigned values for missing data; they matter for transitory-variance estimates, so consider dropping them or requesting the accuracy codes. In 1997 and 1999 head wages exceed head labor income for 470 and 207 heads, as released.

## Caveats
- 1994-2003: no annual UC, WC, SSI, welfare, child support or help from relatives, and Social Security is a family total including other FU members. `cgm_inc` is therefore narrower in those years.
- Labor income definition break in 1994 (farm and business labor income dropped). For a consistent series add the variables the codebook names. Head farm income and labor part of business income: ER4117/ER4119 (1994), ER6957/ER6959 (1995), ER9208/ER9210 (1996), ER16448/ER16490 (1999), ER20420/ER20422 (2001), ER27908/ER27910 (2005), ER40898/ER40900, ER46806/ER46808, ER52214/ER52216, ER58015/ER58017, ER65195/ER65197, ER71272/ER71274, ER77294/ER77296, ER81621/ER81623, ER85475/ER85477 (2007-2023). Wife labor part of business income: ER4141, ER6981, ER9232, ER16511, ER20444, ER27940, ER40930, ER46838, ER52246, ER58047, ER65225, ER71302, ER77324, ER81651, ER85505. 1997 and 2003 need a codebook lookup.
- Weight series breaks: 1989 reweighting of the core sample (1990-1992 weights), 1993-1996 Release-4 revised longitudinal weights, and core/immigrant weights from 1997. No individual weights are in the extracts, so `psid_person_year` has only the family weight of the person's FU. Add the individual longitudinal and cross-sectional weights in the next extract if needed.
- Wife wages are separate only for 2015-2023. Taxable income is only head+wife combined. Individual employment status starts in 1979, individual education in 1968 (not 1969; 1970-1978 excludes heads and wives). Year of birth is in the extract only for 1988+ (not 1992).
- Occupation is missing for most non-workers from 1975 (CGM footnote 8). The retrospective 1968-1980 codes cover selected heads only.
- Latino families (1990-1995) have zero core weights and missing income in 1994-1995. Use `sample` to drop them.

## How to rerun
```
python3 -I psid/scripts/varmap.py /tmp/it_psid/raw2/J366057.do /tmp/it_psid/raw/J366052.do /tmp/it_psid/raw2/cb.txt /tmp/it_psid/raw/cb.txt > psid/varmap.csv
python3 -I psid/scripts/build.py /tmp/it_psid/raw /tmp/it_psid/raw2          # writes /mnt/project-files/psid/*.parquet
python3 -I psid/scripts/validate.py                                           # writes psid/output/*.csv
```
`cb.txt` is `pdftotext -layout` of each `J3660xx_codebook.pdf`. Run the scripts from outside the raw directories.
