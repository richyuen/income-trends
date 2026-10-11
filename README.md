# Income Trends

Estimating the US labor income process (deterministic age profile of real labor income plus permanent and transitory shocks), replicating Cocco, Gomes and Maenhout (2005) and extending it by education, industry, income group, birth cohort and over time, across PSID, SIPP and CPS ASEC. Feeds a life-cycle model.

## Layout
- `cps/` CPS ASEC 1988-2026 person files (ages 15+, earnings, education, industry, occupation, hours, keys), validation against Census Table P-38, links between adjacent ASEC years. See `cps/README.md`.
- `sipp/` SIPP person-year annual earnings, 1995-2024, linked within panel (1996, 2001, 2004, 2008 panels; 2014 panel; SIPP 2018-2025 files), with longitudinal weights and imputation flags. See `sipp/README.md`.
- `cpi/` annual price indexes (CPI-U, C-CPI-U, PCE, and the Census income-table deflator), `cpi/data/price_indexes_annual.csv`.
- `psid/` PSID 1968-2023 family-year panel for the CGM (2005) labor income process: code, hand-checked variable map and aggregate validation tables only. The person-level panels go to `/mnt/project-files/psid/`. **Raw PSID files and person-level data are never committed** (PSID conditions of use). See `psid/README.md`.
- `cgm/` Step 2: replication of the CGM (2005) income process from the PSID panel (fixed-effects age profiles by education, age polynomials, replacement rates, Carroll-Samwick shock variances, correlation with stock returns), each compared with CGM's Tables 1-3. See `cgm/README.md`.

## Conventions
- Data straight from Census (not IPUMS); raw downloads in `/tmp`, outside the repo; scripts take the raw directory as their first argument and download what is missing.
- Nominal dollars in the extracts; deflate with `cpi/`. Income year = survey year - 1 for CPS ASEC and SIPP 2018+ files.
- Python 3 with pandas and pyarrow (`python3 -m pip install pandas pyarrow openpyxl`).
