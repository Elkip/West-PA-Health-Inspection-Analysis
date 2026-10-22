.DEFAULT_GOAL := help
PYTHON ?= python3
RSCRIPT ?= Rscript
QUARTO ?= quarto

.PHONY: help summaries markdown html pdf audit test check-html

help:
	@printf '%s\n' 'summaries   Build summary CSVs' 'markdown    Build summaries and Markdown reports' 'html        Build summaries and interactive HTML' 'pdf         Build summaries and PDF reports' 'audit       Build summaries and refresh the coverage audit' 'test        Run offline R/Python checks' 'check-html  Render HTML and run browser checks'

summaries:
	$(RSCRIPT) scripts/build_summaries.R

markdown: summaries
	$(RSCRIPT) scripts/render_reports.R

html: summaries
	$(QUARTO) render --to html

pdf: summaries
	$(QUARTO) render --to pdf

audit: summaries
	$(PYTHON) scraper/audit_coverage.py --refresh

test:
	$(RSCRIPT) tests/test_inspection_analysis.R
	$(RSCRIPT) tests/test_facility_scope.R
	$(RSCRIPT) tests/test_followup_matching.R
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

check-html: html
	$(PYTHON) tests/check_interactive_report.py
