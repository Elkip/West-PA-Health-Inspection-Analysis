# Allegheny County Food Inspection Analysis

Mitchell Henschel

A reproducible analysis of recorded food-safety violations, establishment rankings, and follow-up inspections in Allegheny County. Historical WPRDC exports are combined with assessment reports downloaded from Accela. Interactive charts let readers explore categories and select restaurants to inspect their visit history.

## Start here

- **Report sources:** [2025](reports/2025.qmd) · [2026](reports/2026.qmd)
- **Methodology and data coverage:** [Permanent-establishment scope and the 2025 source break](docs/data-coverage.md)
- **Data collection:** [Scraper workflow](scraper/README.md)

The ranking uses inspectors' high/medium/low flags, prioritizes high-severity categories, and retains an analyst-defined 5/3/1 score as a secondary view. Permanent-establishment scope and inspection purpose are handled explicitly. The post-August 2025 PDF sample is incomplete; missing reports are not treated as clean inspections.

## Project layout

```text
R/                     Reusable scoring, scope, plotting, and interaction functions
scripts/               Build summaries and render Markdown reports
reports/               Annual Quarto sources
  assets/              Authored JavaScript and CSS for interactive reports
scraper/               Download, parse, and audit source data
  tools/               Manual portal exploration and debugging utilities
docs/                  Methodology and coverage findings
tests/                 Scoring, scope, scraper, and browser checks
data/                  Local CSV inputs and downloaded PDFs (ignored)
out/                   Generated summaries and reports (ignored)
  reports/             Markdown reports and their generated assets
  site/                Quarto HTML/PDF output
_quarto.yml            Shared project paths and annual report list
Makefile               Shortcuts for the workflow below
```

## Setup

Run commands from the **repository root**. Use R 4.1+ (`dplyr` 1.1.0+), Python 3.9+, and Quarto for HTML/PDF rendering. PDF output also requires a TeX installation.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r scraper/requirements.txt
python3 -m playwright install chromium

Rscript -e 'install.packages(c("dplyr", "tidyr", "ggplot2", "stringr", "scales", "knitr", "yaml", "plotly", "htmlwidgets", "htmltools"), repos="https://cloud.r-project.org")'
```

## Workflow

### 1. Acquire the inputs

Download the two historical resources from [WPRDC](https://data.wprdc.org/dataset/allegheny-county-restaurant-food-facility-inspection-violations) into:

- `data/wprdc_inspections.csv` — historical inspections, resource `4ea730d8-2bf9-4783-b0a5-b41ed687097e`
- `data/wprdc_violations.csv` — historical violations, resource `1a1329e2-418c-4bd3-af2c-cc334e7559af`

To collect or refresh Accela attachments:

```bash
python3 scraper/accela_scraper.py --refresh-records
```

This searches permanent permits and stores PDFs and download metadata under `data/accela_downloads/`. See the [scraper guide](scraper/README.md) for discovery and retry details.

### 2. Parse, combine, and summarize

```bash
python3 scraper/scrape_pdfs.py --combine
Rscript scripts/build_summaries.R
```

The parser writes the combined `data/inspections.csv` and `data/violations.csv`. The R pipeline writes inspection/year summaries, severity counts, coverage, and scope decisions to `out/`.

### 3. Check coverage

```bash
python3 scraper/audit_coverage.py --refresh
```

This compares the local PDF sample with the separately cached restored WPRDC inventory. Review `out/source_coverage_audit.json`, `out/source_coverage_by_month.csv`, and `out/inspection_scope_audit.csv` alongside the [coverage findings](docs/data-coverage.md).

### 4. Render the reports

```bash
# Both annual Markdown reports; no Quarto or TeX required
Rscript scripts/render_reports.R

# Both interactive HTML reports
quarto render --to html
```

| Format | Generated files |
|:--|:--|
| Markdown | `out/reports/2025.md`, `out/reports/2026.md` |
| Markdown assets | `out/reports/2025_markdown_files/`, `out/reports/2026_markdown_files/` |
| Interactive HTML | `out/site/reports/2025.html`, `out/site/reports/2026.html` |
| PDF (`quarto render --to pdf`) | `out/site/reports/2025.pdf`, `out/site/reports/2026.pdf` |

Open the HTML files in a browser to use hover, zoom, and restaurant selection. Each HTML report embeds its chart dependencies. Generated reports and Markdown assets are kept locally and excluded from Git; commit the Quarto sources and authored assets instead.

For one year, use `Rscript scripts/render_reports.R 2025` or `quarto render reports/2025.qmd --to html`. Render only years represented in your input data.

## Shortcuts and checks

With dependencies installed and the Python environment activated:

```bash
make summaries     # Build summary CSVs from the combined inputs
make markdown      # Build summaries and Markdown reports
make html          # Build summaries and interactive HTML reports
make audit         # Build summaries and refresh the WPRDC coverage audit
make test          # Run offline R and Python checks
make check-html    # Render HTML and run browser interaction checks
```

The browser check uses `/usr/bin/chromium`. You can choose a Python interpreter explicitly, for example `make test PYTHON=.venv/bin/python`.

See [tests/README.md](tests/README.md) for individual checks and their prerequisites. Live portal debugging scripts are in [scraper/tools/](scraper/tools/README.md).
