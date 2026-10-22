#!/usr/bin/env python3
"""
Download inspection reports from Accela Citizens Access portal.

The attachments are in an iframe and use JavaScript postbacks for downloads.
This script handles that complexity.
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
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "accela_reports"
METADATA_FILE = OUTPUT_DIR / "downloaded_reports.json"

# Date range
START_DATE = datetime(2025, 8, 1)
END_DATE = datetime.now()

# Timeouts (ms)
DEFAULT_TIMEOUT = 10000
DOWNLOAD_TIMEOUT = 30000


async def download_attachment_from_frame(context, frame, link_id: str, output_path: Path) -> bool:
    """
    Download an attachment by clicking the JavaScript link in the iframe.
    """
    try:
        # Set up download handler before clicking
        async with context.expect_event('download', timeout=DOWNLOAD_TIMEOUT) as download_info:
            # Click the download link - this triggers a postback
            await frame.click(f'#{link_id}')
        
        download = await download_info.value
        await download.save_as(output_path)
        return True
        
    except PlaywrightTimeout:
        print(f"      Download timeout for {link_id}")
        return False
    except Exception as e:
        print(f"      Download error: {e}")
        return False


async def get_attachments_from_record(page, context) -> list:
    """
    Get list of attachments from the current record detail page.
    Returns list of dicts with 'name', 'link_id' for each attachment.
    """
    attachments = []
    
    # Activate attachments tab via JavaScript
    try:
        await page.evaluate('''() => {
            const tab = document.querySelector('a[href="#tab-attachments"], a[data-control="tab-attachments"]');
            if (tab) tab.click();
            
            const iframe = document.getElementById('ctl00_PlaceHolderMain_attachmentEdit_iframeAttachmentList');
            if (iframe && (!iframe.src || iframe.src === '')) {
                const url = new URL(window.location.href);
                const params = new URLSearchParams(url.search);
                iframe.src = `/ALLEGHENYCO/FileUpload/AttachmentsList.aspx?module=EnvHealth&capID1=${params.get('capID1')}&capID2=${params.get('capID2')}&capID3=${params.get('capID3')}&agencyCode=ALLEGHENYCO&isdetail=True`;
            }
        }''')
        await asyncio.sleep(2)
    except Exception as e:
        print(f"    Error activating tab: {e}")
        return []
    
    # Find the attachment frame
    attachment_frame = None
    for frame in page.frames:
        if 'AttachmentsList' in frame.url or 'FileUpload' in frame.url:
            attachment_frame = frame
            break
    
    if not attachment_frame:
        return []
    
    # Find file download links (they have id like "attachmentList_gdvAttachmentList_ctl02_lnkFileName")
    try:
        links = await attachment_frame.locator('a[id*="lnkFileName"]').all()
        
        for link in links:
            link_id = await link.get_attribute("id")
            text = await link.text_content()
            if link_id and text:
                attachments.append({
                    "name": text.strip(),
                    "link_id": link_id
                })
    except Exception as e:
        print(f"    Error getting attachment links: {e}")
    
    return attachments


async def process_record(page, context, record_url: str, record_id: str) -> list:
    """Process a single record and download its attachments."""
    downloaded = []
    
    print(f"  Processing: {record_id}")
    
    # Navigate to record
    try:
        await page.goto(record_url, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT)
    except PlaywrightTimeout:
        print(f"    Timeout loading record page")
        return []
    
    await asyncio.sleep(1)
    
    # Get attachments
    attachments = await get_attachments_from_record(page, context)
    
    if not attachments:
        print(f"    No attachments found")
        return []
    
    print(f"    Found {len(attachments)} attachment(s)")
    
    # Find the attachment frame again for downloading
    attachment_frame = None
    for frame in page.frames:
        if 'AttachmentsList' in frame.url or 'FileUpload' in frame.url:
            attachment_frame = frame
            break
    
    if not attachment_frame:
        print(f"    Could not find attachment frame for download")
        return []
    
    # Download each attachment
    for att in attachments:
        safe_name = re.sub(r'[^\w\-.]', '_', att['name'])
        output_path = OUTPUT_DIR / record_id / safe_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_path.exists():
            print(f"    Skipping (exists): {att['name']}")
            downloaded.append({"record": record_id, "file": att['name'], "path": str(output_path)})
            continue
        
        print(f"    Downloading: {att['name']}")
        success = await download_attachment_from_frame(context, attachment_frame, att['link_id'], output_path)
        
        if success:
            downloaded.append({"record": record_id, "file": att['name'], "path": str(output_path)})
            print(f"    ✓ Downloaded: {att['name']}")
        else:
            print(f"    ✗ Failed: {att['name']}")
    
    return downloaded


async def search_records_by_date(page, start_date: datetime, end_date: datetime) -> list:
    """Search for Permanent Food Facility Permit records in date range."""
    records = []
    
    print(f"Searching {start_date.date()} to {end_date.date()}...")
    
    await page.goto(SEARCH_URL, timeout=DEFAULT_TIMEOUT)
    await page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT)
    await asyncio.sleep(1)
    
    # Set date range
    await page.fill('#ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate', start_date.strftime("%m/%d/%Y"))
    await page.fill('#ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate', end_date.strftime("%m/%d/%Y"))
    
    # Select Permanent Food Facility Permit
    try:
        await page.select_option('#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType', label="Permanent Food Facility Permit")
        await asyncio.sleep(0.5)
    except:
        print("  Could not select permit type")
    
    # Search
    await page.click('#ctl00_PlaceHolderMain_btnNewSearch')
    
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    await asyncio.sleep(2)
    
    # Get record links
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
    
    print(f"  Found {len(records)} records")
    return records


async def main():
    """Main scraping routine."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing metadata
    if METADATA_FILE.exists():
        with open(METADATA_FILE) as f:
            metadata = json.load(f)
    else:
        metadata = {"downloads": [], "last_date": None}
    
    downloaded_records = set(d["record"] for d in metadata.get("downloads", []))
    
    print(f"Starting scrape from {START_DATE.date()} to {END_DATE.date()}")
    print(f"Already have {len(downloaded_records)} records")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True
        )
        page = await context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)
        
        try:
            # Process week by week
            current = START_DATE
            while current <= END_DATE:
                week_end = min(current + timedelta(days=7), END_DATE)
                
                records = await search_records_by_date(page, current, week_end)
                
                for record in records:
                    if record["id"] in downloaded_records:
                        continue
                    
                    downloads = await process_record(page, context, record["url"], record["id"])
                    
                    if downloads:
                        metadata["downloads"].extend(downloads)
                        downloaded_records.add(record["id"])
                        
                        # Save after each record
                        metadata["last_date"] = current.isoformat()
                        with open(METADATA_FILE, 'w') as f:
                            json.dump(metadata, f, indent=2)
                
                current = week_end + timedelta(days=1)
                
        finally:
            await browser.close()
    
    print(f"\nDone! Downloaded files from {len(metadata['downloads'])} records")
    print(f"Files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
