# Step 3: the income process by group, over time and across data sources

Step 3 of the plan extends the Cocco, Gomes and Maenhout (2005, "CGM") income process replicated in `cgm/`:

log Y_it = f(age, Z_it) + v_it + ε_it, with v_it = v_i,t-1 + u_it (permanent shocks, variance σ²_u) and ε_it transitory (σ²_ε),

to education, industry, income group and birth cohort, to periods and rolling windows from 1969 to 2022, and to SIPP and CPS ASEC alongside PSID. Everything is rerunnable Python. The outputs feed step 4 (report and parameter dataset).

```
python3 -I extend/scripts/psid_extend.py      # ~20 min; reads /mnt/project-files/psid (private), writes extend/output/psid_*.csv
python3 -I extend/scripts/census_extend.py    # ~4 min; reads sipp/data and cps/data, writes extend/output/{sipp,cps}_*.csv
python3 -I extend/scripts/compare.py          # seconds; writes source_compare.csv and parameters.csv
```

## Method (PSID)
- **Sample** (Richard's default, 2026-10-10): CGM's sample extended to survey 2023: SRC male heads, ages 20-65 (22-65 for college), not retired, housewife or student, **dropping real CGM income under $2,000 (1992 dollars)**. The full sample (positive income) is the robustness check (`sample = full`).
- **Estimator**: unchanged from CGM. A fixed-effects regression of log income on age dummies, marital status and household composition, a cubic fitted to the age dummies, and Carroll-Samwick variances: OLS of Var(r_d) on d, with r_d = u_{t+d} − u_t. Each group and each period is estimated separately, as CGM do for education. Lags d are calendar years, so after 1997 the biennial waves contribute even lags only. Up to 22 lags are used for the long periods (`cgm`, `full`) and 11 for the others.
- **Standard errors**: `s2_*_se` come from a Poisson bootstrap over units (200 draws), with the first-stage residuals held fixed. Unlike CGM's t-ratios, which treat the 22 lag variances as independent observations, they allow for the same people appearing at every lag.
- **Aggregate shocks**: the `_yd` columns demean r_d by start year as well as lag, which removes aggregate shocks. The permanent variance moves by 0.001 or less and the transitory by 0.002 on average (at most 0.007), so the variances are idiosyncratic risk.
- **Replacement rate** (Richard's definition, `repl_prof65_pens`): mean income including pensions of retired SRC male heads aged 65-75 in the period, divided by the group's fitted level at 65 (cubic, with marital status and household composition at sample means). Retirees are grouped by education in the wave, or by their industry, income quintile or cohort from their own working years.
- **Cuts**
  - `education`: the head's group in each wave.
  - `industry`: 7 sectors, the person's modal sector in the period (`incproc.industry_sector` harmonizes the Census 1970/1980/1990 and 2000-2017 codes).
  - `income_q`: quintile of the person's mean log income relative to his age and year ("lifetime" rank).
  - `income_q_init`: the same rank from his first 3 sample years, estimated on his later years only. The ranking years then never enter the variances, which avoids the mechanical link between rank and transitory shocks.
  - `cohort`: birth decade.
- **Periods** (income years): `cgm` 1969-1991, `full` 1969-2022, `p1` 1969-1980, `p2` 1981-1992, `p3` 1993-2006, `p4` 2007-2022. Rolling 12-year windows start every second year from 1969 to 2011.
- **Measures**: `cgm` is CGM's household income (head and wife labor income plus transfers; the default). `head_earn` is the head's own labor income with no household controls, the PSID counterpart of the SIPP and CPS person earnings.

## Results

### 1. Trends over time (PSID, CGM income, default sample; `psid_estimates.csv`, `psid_rolling.csv`)
| Income years | σ²_u permanent | σ²_ε transitory | Rise 25→50 (log pts) | Change 50→60 | Peak age | Replacement rate |
|---|---|---|---|---|---|---|
| 1969-1980 | 0.012 (se 0.002) | 0.070 (0.004) | 0.42 | −0.19 | 44 | 0.56 |
| 1981-1992 | 0.025 (0.002) | 0.061 (0.004) | 0.61 | −0.09 | 48 | 0.56 |
| 1993-2006 | 0.021 (0.002) | 0.103 (0.005) | 0.70 | −0.08 | 50 | 0.69 |
| 2007-2022 | 0.022 (0.002) | 0.087 (0.004) | 0.77 | −0.08 | 48 | 0.85 |
| All, 1969-2022 | 0.015 (0.001) | 0.093 (0.003) | 0.51 | −0.11 | 47 | 0.72 |

- **Permanent risk doubled between the 1970s and the 1980s and has stayed there.** It rises from 0.012 to 0.025 and has been about 0.020-0.025 since. In the rolling windows it is 0.012 in 1969-80, 0.016-0.020 in the windows that follow, 0.025 in 1981-92, and mostly 0.018-0.025 since (one low window, 1989-2000, at 0.011). Over the whole period, which uses up to 22 lags instead of 11, it is 0.015.
- **Transitory risk rose in the 1990s.** It goes from 0.06-0.07 (1970s-80s windows) to 0.10-0.11 (windows of 1989-2012), then falls back to 0.08 in 2009-20 and 2011-22. Part of the step at 1993 is PSID's own: the 1993 move to computer-assisted interviews, the 1994-2003 transfers annualized from as-reported amounts, and imputation mass points in 1997 and 1999 (`psid/README.md`). Head earnings alone show the same rise (0.083 to 0.120), so transfers are not the cause.
- **The age profile has become steeper and flatter after 50.** Income growth from 25 to 50 nearly doubles (0.42 to 0.77 log points), and the fall from 50 to 60 shrinks from 0.19 to 0.08. Like CGM's, these profiles include the aggregate growth of each window (there are no year effects). They therefore swing with the cycle: windows ending in the early 1980s or containing the 2000s and the Great Recession are flatter and fall more after 50.
- **Replacement rates rise over time,** from 0.56 to 0.85. This is noisy because the level at 65 comes from a 12-16 year window.

### 2. By education (`cut = education`)
| | σ²_u: no HS / HS / college | σ²_ε: no HS / HS / college | Replacement rate |
|---|---|---|---|
| CGM window 1969-1991 | 0.012 / 0.011 / 0.018 | 0.089 / 0.082 / 0.065 | 0.82 / 0.77 / 0.68 |
| All years 1969-2022 | 0.013 / 0.011 / 0.018 | 0.109 / 0.095 / 0.085 | 0.85 / 0.78 / 0.72 |
| 1981-1992 | 0.018 / 0.024 / 0.025 | 0.084 / 0.059 / 0.057 | 0.86 / 0.57 / 0.53 |
| 2007-2022 | 0.020 / 0.021 / 0.023 | 0.142 / 0.090 / 0.069 | 1.13 / 0.88 / 0.66 |

- The CGM-window row reproduces step 2's sensitivity run exactly (dropping incomes under $2,000), which checks the new code.
- **Transitory risk falls with education, and the gap has widened.** No high school is 0.142 against 0.069 for college in 2007-22. **Permanent risk has converged** at 0.020-0.023 for all three groups.
- **Richard's default replacement rates (0.87 / 0.78 / 0.68)** come from the full sample in the CGM window. The default sample gives 0.82 / 0.77 / 0.68 in that window and 0.85 / 0.78 / 0.72 over 1969-2022.

### 3. By industry, income group and cohort (all years 1969-2022)
| Industry | σ²_u | σ²_ε | Rise 25→50 | Replacement |
|---|---|---|---|---|
| Agriculture, mining, construction | 0.015 | 0.144 | 0.40 | 0.72 |
| Manufacturing | 0.014 | 0.064 | 0.43 | 0.71 |
| Trade | 0.013 | 0.092 | 0.39 | 0.71 |
| Transport, utilities, information | 0.010 | 0.081 | 0.57 | 0.78 |
| Finance and business services | 0.020 | 0.117 | 0.59 | 0.68 |
| Education, health, other services | 0.015 | 0.102 | 0.69 | 0.86 |
| Public administration | 0.011 | 0.056 | 0.65 | 1.12 |

- **Transitory risk depends on industry more than permanent risk does.** Public administration and manufacturing are lowest (0.056-0.064). Agriculture, mining and construction is highest (0.144). Finance and business services has the highest permanent risk (0.020).
- **Public administration's replacement rate is above 1:** government DB pensions.
- **Industry code seam.** The 3-digit codes put legal, engineering and accounting services in sector 6, and the 2003+ codes put them in sector 5. Public administration's share also drops at 2003, from about 8% to 5.5% of observations, probably because the postal service moves to transportation.

| Income quintile | σ²_u lifetime rank | σ²_ε lifetime rank | σ²_u initial rank | σ²_ε initial rank | Peak age | Replacement |
|---|---|---|---|---|---|---|
| Q1 (lowest) | 0.012 | 0.196 | 0.011 | 0.135 | 36 | 1.06 |
| Q2 | 0.015 | 0.111 | 0.014 | 0.092 | 44 | 0.89 |
| Q3 | 0.012 | 0.084 | 0.015 | 0.076 | 45 | 0.74 |
| Q4 | 0.010 | 0.061 | 0.014 | 0.080 | 48 | 0.70 |
| Q5 (highest) | 0.016 | 0.066 | 0.016 | 0.077 | 52 | 0.52 |

- **Transitory risk is highest for low earners.** It falls from 0.196 (Q1) to 0.06-0.07 (Q4-Q5). Ranking on initial income, so that the ranking years carry no shocks, halves the gap (0.135 to 0.077) but keeps it. Permanent risk is flat across quintiles under the initial-income ranking (0.011-0.016).
- **Profiles differ more by income than by any other cut:** low earners peak at 36, high earners at 52 and keep rising longer. The replacement rate falls from 1.06 (Q1) to 0.52 (Q5), because Social Security replaces more of a low income.
- **Cohorts** (`cut = cohort`): transitory risk is higher for later cohorts: 0.08-0.10 for those born in the 1930s-1950s, 0.11-0.14 for the 1960s-1970s. Permanent risk is 0.013-0.016 for every cohort born 1930-1979. Earlier and later cohorts are seen only late or early in life, so their estimates are noisy and their profiles cover only the ages observed (`age_min`, `age_max`).

### 4. Across data sources: men's own earnings (`source_compare.csv`)
| Source, years | Rise 25→50 | Change 50→60 | Var 1-yr change | σ²_u | σ²_ε | σ²_u, lags 1-4 only | σ²_ε, lags 1-4 only |
|---|---|---|---|---|---|---|---|
| PSID 1981-1992 | 0.52 | −0.19 | 0.171 | 0.029 | 0.083 | 0.041 | 0.069 |
| PSID 1993-2006 | 0.74 | −0.12 | 0.229 | 0.028 | 0.120 | 0.047 | 0.096 |
| PSID 2007-2022 | 0.80 | −0.09 | (biennial) | 0.025 | 0.115 | 0.032 | 0.102 |
| SIPP 1996-2012 (old design) | 0.57 | −0.18 | 0.146 | 0.062 | 0.042 | same | same |
| SIPP 2013-2024 (new design) | 1.11 | −0.01 | 0.253 | 0.056 | 0.098 | same | same |
| CPS 1987-1992 | 0.10 | −0.45 | 0.269 | 0.013 | 0.128 | | |
| CPS 1993-2006 | 0.93 | −0.12 | 0.294 | 0.012 | 0.141 | | |
| CPS 2007-2025 | 1.03 | −0.03 | 0.325 | 0.005 | 0.160 | | |

- **All three sources agree on the direction of change.** Income growth to midlife is steeper and the decline after 50 is smaller in recent decades. The variance of one-year changes has risen in the PSID and the CPS (SIPP's rise is mostly its design break).
- **The levels differ, and the reasons are known.**
  - SIPP's old and new designs differ by a factor of 1.7 in the variance of one-year changes (0.146 against 0.253). That is the 2013 design break, so the two eras are never pooled.
  - CPS one-year changes are the noisiest, at 0.27-0.33. CPS matches people by address, so the changes include matching and reporting error.
  - The CPS profile for 1987-1992 is an artifact: six years of synthetic cohorts that include the 1990-91 recession and falling real wages.
- **Permanent risk cannot be pinned down from short panels.** With only lags 1-4, the PSID gives 0.032-0.047, 1.3-2.2 times its long-lag estimate. SIPP panels (2-4 years per person) allow only those short lags and give 0.056-0.062. The CPS cross-section method (Deaton-Paxson: the rise of within-cohort variance with age) gives 0.005-0.013. So the split between permanent and transitory risk should come from the PSID's long panel. SIPP and CPS serve as checks on the profile, on the total variance of changes and on the trend.

## Recommendations for the life cycle model
- **Baseline: PSID, CGM income, default sample, by education, all years 1969-2022** (`parameters.csv`, `period = full`):
  - σ²_u = 0.013 / 0.011 / 0.018
  - σ²_ε = 0.109 / 0.095 / 0.085
  - the age-profile cubic in `p3_c0`...`p3_c3`, with `const`, `married`, `hhcomp` and their sample means
  - replacement rates 0.87 / 0.78 / 0.68 (Richard's default)
- **For a "today" calibration, use 2007-2022:** σ²_u 0.020 / 0.021 / 0.023, σ²_ε 0.142 / 0.090 / 0.069. The profile is steeper to midlife and flatter after 50.
- **Industry and income-group parameters** are in the same file (`cut = industry`, `income_q`, `income_q_init`).

## Files (`output/`)
| File | What |
|---|---|
| `parameters.csv` | Model-ready parameters: CGM income, default sample, every cut × period. Profile cubic, constant, marital and household coefficients with means, level at 65, σ²_u and σ²_ε with bootstrap SEs and year-demeaned versions, replacement rate and number of retirees. |
| `psid_estimates.csv` | Every PSID estimate (both measures, both samples), including fixed-effects statistics. |
| `psid_profiles.csv` | Age dummies, cubic and income level (thousands of 1992 dollars) by age for each estimate. |
| `psid_var_by_lag.csv` | Var(r_d), mean and pairs for every lag and estimate. |
| `psid_rolling.csv` | The rolling 12-year windows (all and by education, both measures). |
| `sipp_estimates.csv`, `sipp_profiles.csv`, `sipp_var_by_lag.csv` | SIPP by era (all, education, industry) and by panel. |
| `cps_estimates.csv`, `cps_profiles.csv` | CPS by period: synthetic-cohort profile, Deaton-Paxson σ²_u, Var(Δ1) from matched pairs, implied σ²_ε. |
| `cps_var_d1_by_year.csv`, `cps_xs_by_year.csv` | CPS variance of one-year changes by year (1987-2013) and the cross-sectional mean and variance of log earnings by year, men 25-60. |
| `source_compare.csv` | The cross-source table in section 4, with the lags 1-4 fit for PSID and SIPP. |

Scripts: `incproc.py` (shared estimators and the industry crosswalk), `psid_extend.py`, `census_extend.py`, `compare.py`. SIPP and CPS samples: men aged 20-65 with real earnings of at least $2,000 (1992 dollars), no imputed earnings. SIPP also requires full-year records with no top-coded month. Education for SIPP comes from `educ4`, for CPS from `a_hga` (grade completed to 1991, degree from 1992).

## Caveats
- **PSID only:** results cover male heads in the SRC sample, as in CGM. The SEO, immigrant and Latino samples are excluded, and nothing is weighted.
- **Profiles carry the cycle:** profiles from short windows include aggregate growth and recessions (CGM's method has no year effects). Compare shapes across periods, not exact peaks.
- **Short panels and lag range:** SIPP permanent variances come from 2-4 years per person and are not comparable in level with the PSID's. Within PSID, the estimates also depend on the lag range used: 22 lags for the long periods, 11 for the others.
- **Classification for the income-group, industry and cohort cuts:** with the lifetime income rank, transitory shocks partly decide the quintile. Use `income_q_init` for the variances. Industry is the person's modal sector, and people who switch sectors count in one only.
- **PSID breaks:** the 1993-1994 CAI and labor-income definition change, the 1997 sample cut, biennial waves from 1997, and 1997/1999 imputation mass points.
