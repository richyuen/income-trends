# Replicating the Cocco, Gomes and Maenhout (2005) labor income process

Step 2 of the plan. This re-estimates the income process of Cocco, Gomes and Maenhout (2005, *Review of Financial Studies* 18(2), Section 2.1 and Appendix B; "CGM") from our PSID panel, and compares every number with their Tables 1-3:

log Y_it = f(t, Z_it) + v_it + ε_it, with v_it = v_i,t-1 + u_it (permanent, variance σ²_u) and ε_it transitory (variance σ²_ε).

Run (about 15 seconds): `python3 -I cgm/scripts/replicate.py [PANEL_DIR]`. It reads the private panel in `/mnt/project-files/psid/` (built by `psid/scripts/build.py`; never committed) and writes only aggregate tables to `cgm/output/`.

## What the script does
1. **Sample** (as in CGM, Appendix B): SRC sample (SEO dropped), male heads, survey years 1970-1992 (income years 1969-1991), ages 20-65 (22-65 for college graduates); retirees, housewives and students dropped (`emp_h8` 4, 6, 7; in 1970-1975 code 4 is "retired or disabled"); positive CGM income. A head whose education group changes becomes a new unit.
2. **Income**: `cgm_inc` (head and wife labor income, unemployment and workers' comp, Social Security, SSI, other welfare, child support, help from relatives; see `psid/README.md`), in thousands of 1992 dollars with the CPI-U of the income year.
3. **Table 1**: fixed-effects (within) regression of log income on age dummies (youngest age omitted), marital status (spouse present) and household composition (FU members besides head and spouse), by education group. Constant as in Stata's `xtreg, fe`.
4. **Table 2**: third- and fifth-order polynomials in age, age²/10, age³/100 (...) fitted by OLS to the age dummies; replacement rate.
5. **Table 3**: Carroll-Samwick variance decomposition. With r_d = u_{t+d} - u_t, the residual log income u = log Y - f̂(t, Z) differenced within unit for d = 1...22, Var(r_d) = d·σ²_u + 2σ²_ε. The main estimate is OLS of the 22 sample variances on d and a constant (Appendix B, Eq. 19); its t-ratios follow CGM's pattern (college highest). A pooled version (OLS of every squared difference on d, SEs clustered by unit) and a version dropping d = 1, 2 are also reported.
6. **ρ**: the yearly cross-sectional mean of r_1 (the aggregate permanent shock) regressed on demeaned excess stock returns. We use the Fama-French market excess return (CRSP value-weighted, all exchanges, minus the one-month T-bill; `data/ff_market_annual.csv`, from Ken French's data library, downloaded 2026-10-10); CGM used the NYSE value-weighted return.

## Results against CGM

**Sample (Table 1).** We get 1,139 / 2,919 / 1,134 units (no high school / high school / college) against CGM's 1,104 / 2,816 / 1,110, with T-bar 8.47 / 9.61 / 11.27 (CGM 8.58 / 9.57 / 11.06). We drop 167 observations with zero or negative income (0.33%; CGM 326, 0.495%).

**Fixed-effects regression (Table 1).** `output/table1_fixed_effects.csv`

| | No HS: ours | CGM | HS: ours | CGM | College: ours | CGM |
|---|---|---|---|---|---|---|
| Family size | -0.024 (t -4.1) | -0.018 (-3.1) | -0.027 (-7.8) | -0.024 (-7.4) | -0.021 (-4.2) | -0.023 (-4.6) |
| Marital status | 0.373 (15.8) | 0.401 (18.5) | 0.469 (42.3) | 0.444 (43.2) | 0.481 (29.9) | 0.483 (30.5) |
| Constant | 2.725 | 2.628 | 2.726 | 2.700 | 2.365 | 2.383 |
| σ²_e | 0.190 | 0.158 | 0.141 | 0.116 | 0.130 | 0.119 |
| R² within | 0.068 | 0.065 | 0.124 | 0.140 | 0.251 | 0.261 |
| F | 13.2 | 12.3 | 75.6 | 83.1 | 86.6 | 87.2 |

CGM's t-statistics match conventional (not clustered) standard errors; the clustered ones are in the CSV.

**Age profile (Table 2).** `output/table2_age_polynomial.csv`, `output/age_profiles.csv` (age dummies, our cubic and quintic fits, CGM's cubic)

| Cubic | No HS: ours | CGM | HS: ours | CGM | College: ours | CGM |
|---|---|---|---|---|---|---|
| Constant | -1.9396 | -2.1361 | -2.0485 | -2.1700 | -4.0549 | -4.3148 |
| Age | 0.1496 | 0.1684 | 0.1565 | 0.1682 | 0.2983 | 0.3194 |
| Age²/10 | -0.0292 | -0.0353 | -0.0284 | -0.0323 | -0.0509 | -0.0577 |
| Age³/100 | 0.0016 | 0.0023 | 0.0015 | 0.0020 | 0.0027 | 0.0033 |
| Peak age | 37 | 38 | 41 | 44 | 46 | 45 |
| Growth from youngest age to peak | ×1.49 | ×1.53 | ×1.76 | ×1.86 | ×3.18 | ×3.04 |
| Replacement rate | 0.44 | 0.890 | 0.37 | 0.682 | 0.29 | 0.939 |

The rise to the peak matches closely. After 50 our profiles fall more for the two non-college groups: from peak to 65 the cubic drops 0.56 (no HS) and 0.36 (HS) log points, against 0.22 and 0.07 in CGM's cubic. College is closer (0.36 against 0.25, and 1.13 at 65 in both). Keeping only heads who are working or temporarily laid off (dropping the disabled and unemployed) lifts the age-65 value by 0.24 (no HS) and 0.15 (HS) but does not close the gap. Our levels match their Figure 1: exp(constant + age dummy) peaks at about 24,500 / 29,700 / 47,900 1992 dollars, against roughly 22,000 / 29,000 / 45,000 read off the figure.

**Replacement rate: not reproduced.** Ours is the mean CGM income in retirement over the mean in the last working year, for SRC male heads seen moving from work to retirement at 50+ (retired income from the first income year fully in retirement; 265 / 272 / 92 retirees in 1970-1992, 397 / 744 / 408 through 2023, which gives 0.47 / 0.41 / 0.30). A cross-sectional version (retired heads 65-75 against working heads 60-65) gives 0.41 / 0.36 / 0.26. CGM's 0.89 / 0.68 / 0.94 are about twice as high and do not rise with less education as Social Security replacement rates do. The CGM income definition has no private pensions or annuities, so retired income is mostly Social Security and a spouse's earnings. Their numbers probably include pension income, or use a different denominator; the paper does not say. Matching them would need head and wife pension and annuity income from the PSID (a fourth extract).

**Shock variances (Table 3).** `output/table3_variances.csv`, `output/var_by_lag.csv`

| | No HS: ours | CGM | HS: ours | CGM | College: ours | CGM |
|---|---|---|---|---|---|---|
| σ²_ε transitory | 0.123 (t 6.4) | 0.106 (13.3) | 0.099 (14.7) | 0.074 (22.0) | 0.060 (12.7) | 0.058 (13.1) |
| σ²_u permanent | 0.018 (6.0) | 0.011 (9.9) | 0.013 (12.8) | 0.011 (24.3) | 0.022 (30.4) | 0.017 (29.2) |
| ρ with excess returns | -0.04 (β t -0.2) | -0.014 (-0.2) | -0.01 (-0.06) | 0.006 (0.1) | -0.08 (-0.4) | -0.018 (-0.5) |

Our variances are 3-34% higher (transitory) and 24-69% higher (permanent), with the same ordering across groups: transitory risk falls with education and permanent risk is highest for college graduates. The correlation with stock returns is near zero and insignificant in every group, as in CGM (also with next year's return: -0.16 to -0.27, t ≤ 1.3).

**Why our variances are higher** (`output/sensitivity_variances.csv`). The gap comes from a few very low incomes. Observations under $2,000 (1992 dollars) are 0.3% of the high-school sample but 16% of its residual sum of squares. Dropping them gives 0.089 / 0.082 / 0.065 (transitory) and 0.012 / 0.011 / 0.018 (permanent), close to CGM's numbers. Trimming the top and bottom 0.5% of residuals gives 0.082 / 0.066 / 0.055 and 0.013 / 0.009 / 0.013. CGM say they dropped only zeros, but their PSID release is 20 years older, and PSID has since revised and re-imputed income for these waves. Splitting the window, permanent variances are 0.012-0.016 in income years 1969-1980 and 0.019-0.028 in 1981-1991, the rise in earnings instability documented in the literature. Using one unit per person (modal education, no splitting) changes little.

## Takeaways for the life cycle model
- CGM's age profiles and shock variances are reproduced closely in shape and roughly in size. The high-school group, CGM's benchmark (σ²_ε 0.0738, σ²_u 0.0106), comes out at 0.099 and 0.013 on our data, or 0.082 and 0.011 without incomes under $2,000.
- The late-career decline is steeper in our data for non-college households; that matters for the income a model household carries into retirement.
- CGM's replacement rates are not reproducible from their stated income definition; we would rather estimate retirement income directly in step 3, with pension income if Richard requests it from the PSID.

## Decisions for step 3 (Richard, 2026-10-10)
- **Default sample drops observations with real CGM income under $2,000 (1992 dollars)**; the full sample stays as a robustness check.
- Retirement income will be estimated with pension and annuity income from a fourth PSID extract (request list: `/mnt/project-files/notes/psid-extract4-guide.md`).

## Files
| Path | What |
|---|---|
| `scripts/replicate.py` | The whole replication; prints the tables. |
| `data/ff_market_annual.csv` | Fama-French annual market excess return and T-bill rate, 1927-2025 (percent). |
| `output/table1_fixed_effects.csv` | Table 1, ours and CGM's (`cgm_` columns), plus clustered t-statistics and the variance of the fixed effects. |
| `output/table2_age_polynomial.csv` | Cubic (`p3_c0`...) and quintic (`p5_c0`...) coefficients, peak ages, growth to peak, replacement rates (three versions), CGM's values. |
| `output/table3_variances.csv` | Shock variances (22-point OLS, pooled, d ≥ 3), ρ (same-year and next-year returns), CGM's values. |
| `output/age_profiles.csv` | Age dummies, cubic and quintic fits, CGM's cubic, and the level in thousands of 1992 dollars at sample means of marital status and family size. |
| `output/fe_coefficients.csv` | Every fixed-effects coefficient with conventional and clustered SEs. |
| `output/var_by_lag.csv` | Var(r_d), mean and number of pairs for d = 1...22. |
| `output/sensitivity_variances.csv` | Shock variances under the alternative samples above. |
