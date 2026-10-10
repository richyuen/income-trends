# Income Trends

Estimating the US labor income process (deterministic age profile of real labor income plus permanent and transitory shocks), replicating Cocco, Gomes and Maenhout (2005) and extending it by education, industry, income group, birth cohort and over time, across PSID, SIPP and CPS ASEC. Feeds a life-cycle model.

## Layout
- `cps/` CPS ASEC 1988-2026 person files (ages 15+, earnings, education, industry, occupation, hours, keys), validation against Census Table P-38, links between adjacent ASEC years. See `cps/README.md`.
- `sipp/` SIPP person-year annual earnings, 1995-2024, linked within panel (1996, 2001, 2004, 2008 panels; 2014 panel; SIPP 2018-2025 files), with longitudinal weights and imputation flags. See `sipp/README.md`.
- `cpi/` annual price indexes (CPI-U, C-CPI-U, PCE, and the Census income-table deflator), `cpi/data/price_indexes_annual.csv`.
- `psid/` (to come) PSID code only. **Raw PSID files are never committed** (PSID conditions of use).

## Conventions
- Data straight from Census (not IPUMS); raw downloads in `/tmp`, outside the repo; scripts take the raw directory as their first argument and download what is missing.
- Nominal dollars in the extracts; deflate with `cpi/`. Income year = survey year - 1 for CPS ASEC and SIPP 2018+ files.
- Python 3 with pandas and pyarrow (`python3 -m pip install pandas pyarrow openpyxl`).
