# Permanent-establishment scope and the 2025 source break

Audit date: **October 22, 2026**. The drop after the software transition is primarily a gap in the locally downloaded report sample, not evidence that inspections stopped.

## What WPRDC shows

[WPRDC's dataset](https://data.wprdc.org/dataset/allegheny-county-restaurant-food-facility-inspection-violations) now has **two inspection resources**:

| Resource | Observed dates | Contents |
|:--|:--|:--|
| Historical inspections (`4ea730d8-2bf9-4783-b0a5-b41ed687097e`) | January 2, 2014–July 31, 2025 | 124,674 encounters; facility category codes; joinable historical violation rows |
| Restored inspections (`1c9cf8d8-f3db-4364-b925-d7078c2fb02f`) | August 11, 2025–July 28, 2026 | 9,501 rows / **9,498 distinct inspection IDs**; explicit `facility_type`; no violation details |

The restored feed contains **8,885 distinct `Food Facility` inspections**. The other types are Mobile Food (267), Temporary Food (115), Commissary (104), Shared Kitchen (99), and Fish Fry (28). Three extra rows duplicate the same inspection ID and substantive fields; the audit removes only those exact duplicates. The feed's latest update is August 5, 2026, so it is not a complete inventory through the audit date.

For the **same August 11, 2025–July 28, 2026 window**, the local PDF export contains **1,122 inspections of all types combined**, or **1,092 after the permanent-establishment scope filter**. The filtered count is only 12.3% of the official Food Facility count. This is a **volume comparison**, not an encounter-matched recovery rate: the restored feed's inspection IDs and the PDF/footer IDs are different identifiers.

For example, the restored feed has 913 Food Facility inspections in September 2025, 800 in October, and 738 in November; the local PDF export has only 80, 103, and 91 inspections respectively. An establishment-type mismatch cannot explain that difference.

**Do not merge inventory-only rows into the scoring table as zero-violation inspections.** WPRDC says the other feeds are still being restored. An inspection listed without an available violation report has unknown findings, not zero findings. The restored inventory is used separately as a coverage benchmark.

## Which establishments are included?

The intended scope is the Accela **Permanent Food Facility Permit** record type, whose closest explicit counterpart in the restored WPRDC feed is **`facility_type == "Food Facility"`**. This includes more than restaurants: schools, hospitals, stores, and other fixed-site facilities can qualify. `status`, `permit_status`, and inspection `purpose` do not identify permanent establishments.

The historical exports do **not** have `facility_type` or permit type. The revised pipeline therefore records the evidence behind every decision:

1. An explicit `FSP-PERM-...` record identifies a permanent permit, including when its category is missing. The PDF parser now preserves the parent permit record separately from the report's Client ID.
2. An explicit other Accela permit type, or other restored WPRDC facility type, is outside this scope.
3. For legacy records without a permit type, the allowlist in `R/facility_scope.R` is a **historical permanent-category proxy**, not a verified permit-type crosswalk.
4. Mobile codes **119 and 123**, and temporary/event codes **333, 334, 444, 555**, are excluded. The historical export includes **3,423 mobile inspections overall, including 191 in January–July 2025** (about 3.1% of the historical 2025 inspection count).
5. Codes **101, 102, 120, 121** are held out when no explicit permanent permit is available. These describe transient/shared-kitchen or commissary uses and cannot reliably determine the permit type: the restored feed shows category overlap between Food Facility, Shared Kitchen, and Commissary. Unknown codes are also held out.
6. Fixed-site pool snack bars (including **777**, labeled “Seasonal/Pool Snack Bar”) remain included. The restored feed classifies that category as Food Facility; the word “seasonal” alone does not make it a temporary vendor permit.

ACHD distinguishes [shared-kitchen operators from separately permitted users](https://www.alleghenycounty.us/Services/Health-Department/Food-Safety/Permits-and-Registration/Shared-Kitchens). Its [2026 fee schedule](https://www.alleghenycounty.us/files/assets/county/v/3/government/health/documents/food-safety/food-safety-program-2026-fee-schedule.pdf) also lists mobile and commissary-use permits separately. A blanket “exclude transient/seasonal names” filter would not reproduce those distinctions.

`out/inspection_scope_audit.csv` lists every non-training encounter, the inclusion decision, category, and reason. Both inspections and associated violations are filtered together by encounter ID. Historical results should be described as **permanent-category comparisons**, with ambiguous cases held out, rather than claiming all historical permit types have been verified.

## Download coverage versus PDF parsing

The local attachment snapshot contained **2,358 files**. Re-running the parser yielded **2,337 unique inspections**, **17 duplicate reports**, and **4 unparsed files**. Inspection of those four files showed two inspection cover letters and two liquor-license records, not assessment reports with violation tables. This does not explain the thousands of missing inventory inspections. Many downloaded reports are historical, so 2,337 is not the post-transition count.

The saved scraper metadata had **1,406 processed permit records**, with file downloads associated with **1,114 distinct permits**. “Processed” previously included timeouts and empty attachment scans. The original date-limited search also searched permit dates, not inspection dates, excluding older permits with newer inspections. The user's revised search correctly clears those dates; a live check confirmed the Permanent Food Facility Permit selection and advancement from the first to the second results page. That check does not establish that the entire portal has been traversed.

Additional fixes now:

- Require the intended permit-type selection to succeed.
- Raise an error on stalled/failed pagination instead of treating it as the last page.
- Track successful, empty, missing-frame, and failed attachment scans separately; old `processed_records` entries alone no longer suppress retries.
- Support `--refresh-records` to revisit successful permits for newly added attachments, reusing existing files.
- Export a per-file parser audit instead of calling every unparsed file a confirmed non-inspection document.

Attachment availability and incomplete discovery/download coverage remain possible sources of missing reports. No full portal backfill is claimed by this audit.

## Reproduce and inspect

```bash
python3 scraper/scrape_pdfs.py --combine
Rscript scripts/build_summaries.R
python3 scraper/audit_coverage.py --refresh
Rscript tests/test_facility_scope.R
python3 -m unittest discover -s tests -p test_coverage_audit.py
```

- `data/wprdc_current_inspections.csv` and its metadata sidecar: separately cached restored inventory and retrieval information.
- `data/accela_inspections_pdf_audit.csv`: parsed, duplicate, and unparsed file decisions.
- `out/inspection_scope_audit.csv`: establishment-scope decisions.
- `out/source_coverage_by_month.csv`: same-window monthly inventory and local-PDF counts, including the filtered local subset. Boundary months can be partial.
- `out/source_coverage_audit.json`: counts, date bounds, and deduplication summary.
- `out/wprdc_facility_type_counts.csv`: official type counts.

To backfill/recheck permit attachments, run `python3 scraper/accela_scraper.py --refresh-records` in an environment with Playwright installed. This is a full permit discovery/download run; inspect its completion status and the coverage audit afterward. Then rebuild the reports with `Rscript scripts/render_reports.R` or `quarto render --to html` from the repository root.
