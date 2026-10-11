# Parameter dataset for the life cycle model

Step 4 deliverable. Built by `python3 -I dataset/build_dataset.py` from `extend/output/parameters.csv` (PSID; CGM household income: head and spouse labor income plus transfers, thousands of 1992 dollars, CPI-U; SRC male heads aged 20-65, 22-65 with a college degree; incomes under $2,000 in 1992 dollars dropped).

Model (CGM 2005):

    log Y = const + married*m + hhcomp*h + f(age) + v + e,   f(age) = c0 + c1*age + c2*age^2/10 + c3*age^3/100
    v_t = v_{t-1} + u,   Var(u) = s2_perm,   Var(e) = s2_trans
    retirement income = lambda * exp(const + married*mean_married + hhcomp*mean_hhcomp + f(65))

| File | What |
|---|---|
| `income_process_model.json` | Ready-to-use sets by education: `baseline_1969_2022` (recommended), `recent_2007_2022`, `cgm_window_1969_1991`; each with the profile cubic, constant, controls and their means, shock variances with bootstrap SEs, estimated replacement rate and fitted income at 65. `replacement_rate_default` holds the project's choice, 0.87 / 0.78 / 0.68. |
| `income_process_parameters.csv` | Long format: one row per period x cut x group x parameter, with value, SE (shock variances), unit and description. Cuts: all, education, industry, income_q (lifetime rank), income_q_init (initial rank; use for variances), cohort (all years only). Periods: cgm 1969-1991, full 1969-2022, p1 1969-1980, p2 1981-1992, p3 1993-2006, p4 2007-2022 (income years). |
| `age_profiles.csv` | Fitted income at each age for every period x cut x group: log level, thousands of 1992 dollars and of 2024 dollars (CPI-U factor 2.236), with marital status and household size at sample means. |

Notes: profiles include each period's aggregate real growth (no year effects), as in CGM. Variances are in log points squared. Period-specific replacement rates are noisy; the project uses 0.87 / 0.78 / 0.68. The report (`report/income_process_report.html`, built by `report/build.py`) explains every number; method and caveats are in `extend/README.md`.
