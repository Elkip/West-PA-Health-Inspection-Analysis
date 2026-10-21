#!/usr/bin/env python3
"""
Allegheny County Accela Citizens Access Health Inspection Scraper

Downloads inspection reports (PDF attachments) from permits dated August 2025 onwards.
Requires: pip install playwright
Then run: playwright install chromium
"""

import asyncio
import re
import json
from datetime import datetime, timedelta
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Configuration
BASE_URL = "https://aca-prod.accela.com/ALLEGHENYCO"
SEARCH_URL = f"{BASE_URL}/Cap/CapHome.aspx?module=EnvHealth&TabName=Home"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "accela_downloads"
METADATA_FILE = OUTPUT_DIR / "inspection_metadata.json"

# Date range - August 2025 onwards (when ACHD switched to Accela)
START_DATE = datetime(2025, 8, 11)
END_DATE = datetime.now()

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


async def start_search(page, start_date: datetime, end_date: datetime):
    """
    Start a search for Permanent Food Facility Permit records.
    Returns True if search succeeded.
    """
    print(f"Searching {start_date.date()} to {end_date.date()}...")
    
    try:
        await page.goto(SEARCH_URL, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT)
    except PlaywrightTimeout:
        print("  Timeout loading search page")
        return False
    
    await asyncio.sleep(1)
    
    # Set date range
    await page.fill('#ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate', start_date.strftime("%m/%d/%Y"))
    await page.fill('#ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate', end_date.strftime("%m/%d/%Y"))
    
    # Select Permanent Food Facility Permit
    try:
        await page.select_option('#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType', label="Permanent Food Facility Permit")
        await asyncio.sleep(0.5)
    except:
        pass
    
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


async def go_to_next_page(page) -> bool:
    """Try to go to next page of results. Returns True if successful."""
    next_btn = page.locator('a:has-text("Next >")').first
    
    try:
        if await next_btn.count() == 0:
            return False
        
        if not await next_btn.is_visible():
            return False
        
        await next_btn.click()
        
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        await asyncio.sleep(1)
        
        return True
        
    except:
        return False


async def get_attachments_from_record(page, context, record_url: str, record_id: str) -> list:
    """
    Navigate to record, find attachments, and download them.
    Returns list of downloaded file info.
    """
    downloaded = []
    
    print(f"  {record_id}:", end="", flush=True)
    
    # Navigate to record
    try:
        await page.goto(record_url, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT)
    except PlaywrightTimeout:
        print(" timeout")
        return []
    
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
        return []
    
    # Find file download links
    links = await attachment_frame.locator('a[id*="lnkFileName"]').all()
    
    if not links:
        print(" no attachments")
        return []
    
    print(f" {len(links)} file(s):", end="", flush=True)
    
    # Download each attachment
    for link in links:
        try:
            link_id = await link.get_attribute("id")
            file_name = await link.text_content()
            
            if not link_id or not file_name:
                continue
            
            file_name = file_name.strip()
            safe_name = re.sub(r'[^\w\-.]', '_', file_name)
            output_path = OUTPUT_DIR / record_id / safe_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if output_path.exists():
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
                print(" [timeout]", end="", flush=True)
            except Exception as e:
                print(f" [error: {str(e)[:20]}]", end="", flush=True)
                
        except Exception as e:
            continue
    
    print()  # Newline after record
    return downloaded


async def main():
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
    
    print(f"Scraping from {START_DATE.date()} to {END_DATE.date()}")
    print(f"Already processed {len(processed_records)} records")
    print(f"Output directory: {OUTPUT_DIR}\n")
    
    async with async_playwright() as p:
        browser, context = await setup_browser(p)
        page = await context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)
        
        try:
            # Start search
            if not await start_search(page, START_DATE, END_DATE):
                print("Search failed")
                return
            
            # Collect all record URLs first (fast - just pagination)
            print("Collecting records...", end="", flush=True)
            all_records = []
            seen_ids = set()
            page_num = 1
            
            while True:
                records = await get_records_on_current_page(page)
                if not records:
                    break
                
                # Check if we've seen these records before (stuck on same page)
                new_records = [r for r in records if r["id"] not in seen_ids]
                if not new_records:
                    break  # No new records = we're stuck or looping
                
                for r in new_records:
                    seen_ids.add(r["id"])
                    all_records.append(r)
                
                print(f" p{page_num}", end="", flush=True)
                
                if not await go_to_next_page(page):
                    break
                page_num += 1
            
            print(f" done ({len(all_records)} records)")
            
            # Filter out already processed
            to_process = [r for r in all_records if r["id"] not in processed_records]
            print(f"New records to process: {len(to_process)}\n")
            
            # Process each record
            for i, record in enumerate(to_process):
                downloads = await get_attachments_from_record(page, context, record["url"], record["id"])
                
                # Update metadata
                metadata["downloads"].extend(downloads)
                processed_records.add(record["id"])
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
    asyncio.run(main())
