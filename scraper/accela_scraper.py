#!/usr/bin/env python3
"""
Allegheny County Accela Citizens Access Health Inspection Scraper

Downloads inspection reports from all Permanent Food Facility Permit records.
Permit creation dates are not inspection dates; discovery has no date filter.
Requires: pip install playwright
Then run: playwright install chromium
"""

import asyncio
import argparse
import re
import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Configuration
BASE_URL = "https://aca-prod.accela.com/ALLEGHENYCO"
SEARCH_URL = f"{BASE_URL}/Cap/CapHome.aspx?module=EnvHealth&TabName=Home"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "accela_downloads"
METADATA_FILE = OUTPUT_DIR / "inspection_metadata.json"

# Timeouts (milliseconds)
DEFAULT_TIMEOUT = 15000
DOWNLOAD_TIMEOUT = 30000


async def setup_browser(playwright):
    """Launch browser with appropriate settings."""
    browser = await playwright.chromium.launch(
        headless=True,  # Set to False for debugging
    )
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        accept_downloads=True,
    )
    return browser, context


async def start_search(page):
    """
    Start a search for ALL Permanent Food Facility Permit records (no date filter).
    Returns True if search succeeded.
    """
    print("Searching for all Permanent Food Facility Permits...")
    
    try:
        await page.goto(SEARCH_URL, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT)
    except PlaywrightTimeout:
        print("  Timeout loading search page")
        return False
    
    await asyncio.sleep(1)
    
    # Clear date fields (search all records)
    await page.fill('#ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate', '')
    await page.fill('#ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate', '')
    
    # Select Permanent Food Facility Permit
    try:
        await page.select_option('#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType', label="Permanent Food Facility Permit")
        await asyncio.sleep(0.5)
    except Exception as exc:
        raise RuntimeError("Could not select Permanent Food Facility Permit; refusing an unscoped search") from exc
    selected = await page.locator('#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType option:checked').inner_text()
    if selected.strip() != "Permanent Food Facility Permit":
        raise RuntimeError(f"Unexpected record type selected: {selected}")
    
    # Click search
    await page.click('#ctl00_PlaceHolderMain_btnNewSearch')
    
    try:
        await page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT)
    except:
        pass
    await asyncio.sleep(2)
    
    return True


async def get_records_on_current_page(page) -> list:
    """Get record links from the current search results page."""
    records = []
    links = await page.locator('a[href*="CapDetail"]').all()
    
    for link in links:
        try:
            href = await link.get_attribute("href")
            text = await link.text_content()
            if href and text:
                record_id = text.strip()
                full_url = f"https://aca-prod.accela.com{href}" if href.startswith('/') else href
                records.append({"id": record_id, "url": full_url})
        except:
            pass
    
    return records


async def go_to_next_page(page, retries=3) -> bool:
    """Try to go to next page of results. Returns True if successful."""
    for attempt in range(retries):
        try:
            next_btn = page.locator('a:has-text("Next >")').first

            if await next_btn.count() == 0:
                return False

            if not await next_btn.is_visible():
                raise RuntimeError("Next-page control is unexpectedly hidden")

            # Get current first record to verify page changed
            first_record = None
            first_link = page.locator('a[href*="CapDetail"]').first
            if await first_link.count() > 0:
                first_record = await first_link.text_content()

            await next_btn.click()

            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except:
                pass
            await asyncio.sleep(1.5)

            # Verify page actually changed
            new_first = None
            new_first_link = page.locator('a[href*="CapDetail"]').first
            if await new_first_link.count() > 0:
                new_first = await new_first_link.text_content()

            if first_record and new_first and first_record != new_first:
                return True

            # Page didn't change, retry
            await asyncio.sleep(1)

        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(2)
                continue
            raise RuntimeError("Pagination failed before a verified last page; discovery is incomplete") from e

    raise RuntimeError("Pagination did not advance; discovery is incomplete")


async def get_attachments_from_record(page, context, record_url: str, record_id: str) -> tuple:
    """
    Navigate to record, find attachments, and download them.
    Returns (downloads, status); failed/empty visits must remain retryable.
    """
    downloaded = []
    failed = False
    
    print(f"  {record_id}:", end="", flush=True)
    
    # Navigate to record
    try:
        await page.goto(record_url, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT)
    except PlaywrightTimeout:
        print(" timeout")
        return [], "failed"
    
    await asyncio.sleep(1)
    
    # Activate attachments tab and load iframe
    await page.evaluate('''() => {
        const tab = document.querySelector('a[href="#tab-attachments"]');
        if (tab) tab.click();
        
        const iframe = document.getElementById('ctl00_PlaceHolderMain_attachmentEdit_iframeAttachmentList');
        if (iframe && (!iframe.src || iframe.src === '')) {
            const url = new URL(window.location.href);
            const params = new URLSearchParams(url.search);
            iframe.src = `/ALLEGHENYCO/FileUpload/AttachmentsList.aspx?module=EnvHealth&capID1=${params.get('capID1')}&capID2=${params.get('capID2')}&capID3=${params.get('capID3')}&agencyCode=ALLEGHENYCO&isdetail=True`;
        }
    }''')
    await asyncio.sleep(2)
    
    # Find attachment frame
    attachment_frame = None
    for frame in page.frames:
        if frame.url and ('AttachmentsList' in frame.url or 'FileUpload' in frame.url):
            attachment_frame = frame
            break
    
    if not attachment_frame:
        print(" no attachment frame")
        return [], "missing_attachment_frame"
    
    # Find file download links
    links = await attachment_frame.locator('a[id*="lnkFileName"]').all()
    
    if not links:
        print(" no attachments")
        return [], "no_attachments"
    
    print(f" {len(links)} file(s):", end="", flush=True)
    
    # Download each attachment
    for link in links:
        try:
            link_id = await link.get_attribute("id")
            file_name = await link.text_content()
            
            if not link_id or not file_name:
                failed = True
                continue
            
            file_name = file_name.strip()
            safe_name = re.sub(r'[^\w\-.]', '_', file_name)
            output_path = OUTPUT_DIR / record_id / safe_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if output_path.exists() and output_path.stat().st_size > 0:
                print(" [skip]", end="", flush=True)
                downloaded.append({"record": record_id, "file": file_name, "path": str(output_path)})
                continue
            
            # Download by clicking the link (triggers JS postback)
            try:
                async with context.expect_event('download', timeout=DOWNLOAD_TIMEOUT) as download_info:
                    await attachment_frame.click(f'#{link_id}')
                
                download = await download_info.value
                await download.save_as(output_path)
                print(" ✓", end="", flush=True)
                downloaded.append({"record": record_id, "file": file_name, "path": str(output_path)})
                
            except PlaywrightTimeout:
                failed = True
                print(" [timeout]", end="", flush=True)
            except Exception as e:
                failed = True
                print(f" [error: {str(e)[:20]}]", end="", flush=True)
                
        except Exception as e:
            failed = True
            continue
    
    print()  # Newline after record
    return downloaded, "partial_failure" if failed else "complete"


async def main(refresh_records=False):
    """Main scraping routine."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing metadata
    if METADATA_FILE.exists():
        with open(METADATA_FILE) as f:
            data = json.load(f)
            # Handle old format (list) vs new format (dict)
            if isinstance(data, list):
                metadata = {"downloads": data, "processed_records": [], "last_date": None}
            else:
                metadata = data
    else:
        metadata = {"downloads": [], "processed_records": [], "last_date": None}
    
    processed_records = set(metadata.get("processed_records", []))
    record_status = metadata.setdefault("record_status", {})
    
    print("Discovering all permanent permit records without a permit-date filter")
    print(f"Already processed {len(processed_records)} records")
    print(f"Output directory: {OUTPUT_DIR}\n")
    
    async with async_playwright() as p:
        browser, context = await setup_browser(p)
        page = await context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)
        
        try:
            metadata["discovery_complete"] = False
            with open(METADATA_FILE, "w") as f:
                json.dump(metadata, f, indent=2)
            # Start search
            if not await start_search(page):
                print("Search failed")
                return
            
            # Collect all record URLs first (fast - just pagination)
            print("Collecting records...", end="", flush=True)
            all_records = []
            seen_ids = set()
            page_num = 1
            stuck_count = 0
            
            while True:
                records = await get_records_on_current_page(page)
                if not records:
                    print(" [no records]", end="", flush=True)
                    stuck_count += 1
                    if stuck_count >= 3:
                        raise RuntimeError("Search repeatedly returned no records; discovery is incomplete")
                    await asyncio.sleep(2)
                    continue
                
                # Check if we've seen these records before (stuck on same page)
                new_records = [r for r in records if r["id"] not in seen_ids]
                if not new_records:
                    stuck_count += 1
                    if stuck_count >= 3:
                        raise RuntimeError("Search is stuck on repeated records; discovery is incomplete")
                    await asyncio.sleep(2)
                    continue
                
                stuck_count = 0  # Reset on success
                for r in new_records:
                    seen_ids.add(r["id"])
                    all_records.append(r)
                
                print(f" p{page_num}", end="", flush=True)
                
                if not await go_to_next_page(page):
                    print(" [end]", end="", flush=True)
                    break
                page_num += 1
            
            print(f" ({len(all_records)} records)")
            metadata["discovery_complete"] = True
            metadata["discovered_records"] = all_records
            metadata["discovered_at"] = datetime.now().isoformat()
            with open(METADATA_FILE, "w") as f:
                json.dump(metadata, f, indent=2)
            
            # Filter out already processed
            # Legacy processed_records includes timeouts and empty records. It
            # is not evidence of a successful attachment scan.
            to_process = [r for r in all_records if refresh_records or record_status.get(r["id"], {}).get("status") != "complete"]
            print(f"Records to scan: {len(to_process)}\n")
            
            # Process each record
            for i, record in enumerate(to_process):
                try:
                    downloads, status = await get_attachments_from_record(page, context, record["url"], record["id"])
                except Exception as exc:
                    print(f"  {record['id']}: {exc}")
                    downloads, status = [], "failed"
                
                # Update metadata
                known_paths = {r.get("path") for r in metadata["downloads"]}
                metadata["downloads"].extend(r for r in downloads if r["path"] not in known_paths)
                record_status[record["id"]] = {"status": status, "checked_at": datetime.now().isoformat()}
                if status == "complete":
                    processed_records.add(record["id"])
                else:
                    processed_records.discard(record["id"])
                metadata["processed_records"] = list(processed_records)
                
                # Save after each record
                with open(METADATA_FILE, 'w') as f:
                    json.dump(metadata, f, indent=2)
                    
        finally:
            await browser.close()
    
    print(f"\n{'='*50}")
    print(f"Scraping complete!")
    print(f"Total downloads: {len(metadata['downloads'])}")
    print(f"Records processed: {len(processed_records)}")
    print(f"Files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-records", action="store_true", help="Revisit successful permits for newly added attachments (existing files are reused)")
    asyncio.run(main(refresh_records=parser.parse_args().refresh_records))
