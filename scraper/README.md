# Allegheny County Health Inspection Report Downloaders

Tools for downloading health inspection reports from Allegheny County.

## Background

The Allegheny County Health Department (ACHD) data is available through:

1. **WPRDC** (through July 31, 2025): Historical CSV exports of inspections and violations
2. **Accela Citizens Access** (August 11, 2025+): Permit records with PDF attachments

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
1. Searches for "Permanent Food Facility Permit" records by date range
2. Navigates to each record's detail page
3. Activates the Attachments tab (loads an iframe)
4. Downloads PDF attachments via JavaScript postback links

**Output:**
- PDFs: `data/accela_downloads/RECORD_ID/filename.pdf`
- Metadata: `data/accela_downloads/inspection_metadata.json`

**Configuration (in script):**
```python
START_DATE = datetime(2025, 8, 11)  # When ACHD switched to Accela
END_DATE = datetime.now()
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

## Test Scripts

### `test_download.py`
Test downloading from a specific record:
```bash
python test_download.py
```

### `debug_specific_record.py`
Debug a specific record (FSP-PERM-202610080591):
```bash
python debug_specific_record.py
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
