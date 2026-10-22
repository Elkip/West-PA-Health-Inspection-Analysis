# Manual exploration and debugging tools

These scripts were used to investigate the Accela portal and older download approaches. The supported collection workflow is documented in [scraper/README.md](../README.md).

Run these explicitly from the repository root when troubleshooting:

| Tool | Purpose |
|:--|:--|
| `explore_portal.py` | Inspect the portal's available modules and record types |
| `debug_attachments.py` | Examine attachment frames and links |
| `debug_inspections.py` | Investigate inspection and encounter identifiers |
| `debug_record.py`, `debug_record_details.py` | Inspect record-detail pages |
| `debug_specific_record.py` | Debug the example permit embedded in the script |
| `download_one_record.py` | Manually exercise a single attachment download |
| `download_from_accela.py` | Earlier date-based Accela downloader |
| `download_inspection_reports.py` | Earlier Oracle report downloader |

Example: `python3 scraper/tools/debug_specific_record.py`.

These are live-site tools with example IDs and dates in their source. Offline automated checks live in [`tests/`](../../tests/).
