# Allegheny County Health Inspection Report Downloaders

Tools for downloading health inspection reports from Allegheny County.

## Background

The Allegheny County Health Department (ACHD) data is available through:

1. **WPRDC historical resources** (through July 31, 2025): CSV exports of inspections and violations
2. **Accela Citizens Access** (August 11, 2025+): Permit records with PDF attachments
3. **WPRDC restored inspection inventory** (resource `1c9cf8d8-f3db-4364-b925-d7078c2fb02f`): post-transition inspection metadata with `facility_type`, but no violation details. Use `audit_coverage.py` to compare coverage without treating missing PDFs as clean inspections.

See [the permanent-establishment and source-coverage audit](../docs/data-coverage.md) and the [project workflow](../README.md).

## Installation

```bash
cd scraper
pip install -r requirements.txt
playwright install chromium
```

## Main Script: `accela_scraper.py`

Downloads inspection report PDFs from the Accela Citizens Access portal.

```bash
python accela_scraper.py
```

**What it does:**
1. Searches all "Permanent Food Facility Permit" records with the permit-date fields cleared
2. Navigates to each record's detail page
3. Activates the Attachments tab (loads an iframe)
4. Downloads PDF attachments via JavaScript postback links

**Output:**
- PDFs: `data/accela_downloads/RECORD_ID/filename.pdf`
- Metadata: `data/accela_downloads/inspection_metadata.json`

Use `python accela_scraper.py --refresh-records` to revisit previously successful records for new attachments. Failed and empty scans remain retryable; legacy `processed_records` values are not proof of successful downloads. Pagination failures raise an error and leave `discovery_complete` false.

**Configuration (in script):**
```python
DEFAULT_TIMEOUT = 15000             # 15 seconds
DOWNLOAD_TIMEOUT = 30000            # 30 seconds for downloads
```

## PDF Scraper: `scrape_pdfs.py`

Extracts inspection and violation records from downloaded PDFs in `data/accela_downloads` into CSV files matching the historical `inspections.csv` and `violations.csv` schemas.

```bash
python scrape_pdfs.py
```

**Output:**
- Inspections: `data/accela_inspections.csv`
- Violations: `data/accela_violations.csv`
- Per-file audit: `data/accela_inspections_pdf_audit.csv`

Inspection rows retain `source` and `permit_record_id`. Use `--combine` to rebuild the combined inputs. The R pipeline applies the permanent-establishment filter consistently to inspection and violation rows.

## Coverage audit

After rebuilding the R summaries, run `python scraper/audit_coverage.py --refresh` from the repository root. It caches the restored WPRDC inventory separately and writes same-window comparisons under `out/`. Counts are compared by month; PDF encounter IDs are not assumed to equal the restored feed's inspection IDs.

## Test Scripts

### `tools/download_one_record.py`
Test downloading from a specific record:
```bash
python tools/download_one_record.py
```

### `tools/debug_specific_record.py`
Debug a specific record (FSP-PERM-202610080591):
```bash
python tools/debug_specific_record.py
```

## Technical Notes

### How Accela Attachments Work

1. Record detail pages have an Attachments tab
2. Clicking the tab loads an iframe (`AttachmentsList.aspx`)
3. File links use JavaScript postbacks: `javascript:__doPostBack('attachmentList$gdvAttachmentList$ctl02$lnkFileName','')`
4. Clicking triggers a file download (handled via Playwright's download events)

### Tips

- The iframe may not load automatically - the script triggers it via JavaScript
- Use `context.expect_event('download')` to catch downloads from postback links
- Set `headless=False` in `setup_browser()` to watch the browser for debugging

## Known Limitations

1. **Not all records have attachments**: Many permit records don't have inspection reports attached yet
2. **Rate limiting**: The script includes delays; be respectful of server resources
3. **Session timeouts**: Long-running scrapes may hit session limits

## Legal

These tools access public records. Respect the website's terms of service.
