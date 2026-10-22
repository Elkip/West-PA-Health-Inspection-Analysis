# Verification

Run checks from the repository root with the dependencies in the [setup guide](../README.md#setup).

| Command | What it checks |
|:--|:--|
| `Rscript tests/test_inspection_analysis.R` | Severity scoring, aggregation, input validation, and original-report checks when local data is available |
| `Rscript tests/test_facility_scope.R` | Permanent-establishment scope and synchronized filtering of inspections/violations |
| `Rscript tests/test_followup_matching.R` | Chronological matching, report links, and exclusion rules |
| `python3 -m unittest discover -s tests -p 'test_*.py'` | Coverage comparison, deduplication, and scraper retry/discovery logic; no live network requests |
| `python3 tests/check_interactive_report.py` | Offline HTML rendering, hover/click details, report links, and mobile selection |

`make test` runs the R and Python checks. For the browser check, first generate both reports with `quarto render --to html`; they must exist in `out/site/reports/`. Playwright and `/usr/bin/chromium` are required. `make check-html` builds the reports and runs that check.

The manual tools under [`scraper/tools/`](../scraper/tools/README.md) access the live portal and are not part of this test suite.
