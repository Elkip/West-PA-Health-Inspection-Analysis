#!/usr/bin/env python3
"""Debug script to find records with attachments."""

import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://aca-prod.accela.com/ALLEGHENYCO"


async def find_records_with_attachments():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=50)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print("Searching for Permanent Food Facility Permits...")
        await page.goto(f"{BASE_URL}/Cap/CapHome.aspx?module=EnvHealth&TabName=Home")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Set date range
        await page.locator('#ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate').fill("08/01/2025")
        await page.locator('#ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate').fill("09/30/2025")
        
        # Select Permanent Food Facility Permit
        type_select = page.locator('#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType')
        await type_select.select_option(label="Permanent Food Facility Permit")
        await asyncio.sleep(1)
        
        # Search
        await page.locator('#ctl00_PlaceHolderMain_btnNewSearch').click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        
        # Get all record links
        record_links = await page.locator('a[href*="CapDetail"]').all()
        print(f"Found {len(record_links)} records")
        
        # Check multiple records for attachments
        for i, link in enumerate(record_links[:10]):
            href = await link.get_attribute("href")
            text = await link.text_content()
            record_id = text.strip() if text else f"Record {i}"
            
            print(f"\n--- Checking {record_id} ---")
            
            # Navigate to record
            full_url = f"https://aca-prod.accela.com{href}"
            await page.goto(full_url)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
            
            # Trigger attachment iframe loading
            await page.evaluate('''() => {
                const tab = document.querySelector('a[href="#tab-attachments"]');
                if (tab) tab.click();
                const iframe = document.getElementById('ctl00_PlaceHolderMain_attachmentEdit_iframeAttachmentList');
                if (iframe && (!iframe.src || iframe.src === '')) {
                    const urlParams = new URLSearchParams(window.location.search);
                    iframe.src = `/ALLEGHENYCO/FileUpload/AttachmentsList.aspx?module=EnvHealth&capID1=${urlParams.get('capID1')}&capID2=${urlParams.get('capID2')}&capID3=${urlParams.get('capID3')}&agencyCode=ALLEGHENYCO`;
                }
            }''')
            await asyncio.sleep(2)
            
            # Check attachment frame
            for frame in page.frames:
                if 'AttachmentsList' in frame.url or 'FileUpload' in frame.url:
                    # Look for file download links
                    file_links = await frame.locator('a[id*="lnkFileName"], a[href*="FileViewer"], a[href*=".pdf"]').all()
                    
                    if file_links:
                        print(f"  FOUND {len(file_links)} attachments!")
                        for fl in file_links[:5]:
                            fl_href = await fl.get_attribute("href")
                            fl_text = await fl.text_content()
                            fl_id = await fl.get_attribute("id")
                            print(f"    - id={fl_id} '{fl_text}' -> {fl_href[:60] if fl_href else 'no href'}")
                        
                        # Save the frame HTML for inspection
                        frame_html = await frame.content()
                        with open(f"/tmp/opencode/frame_with_attachments.html", "w") as f:
                            f.write(frame_html)
                        print(f"  Frame HTML saved to /tmp/opencode/frame_with_attachments.html")
                        await browser.close()
                        return
                    else:
                        # Check if there's a "no records" message
                        no_records = await frame.locator('text="No records found"').count()
                        row_count = await frame.locator('table tr').count()
                        print(f"  No file links found (rows: {row_count}, no_records: {no_records})")
            
            # Go back to search results
            await page.go_back()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
        
        print("\nNo records with attachments found in first 10 results")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(find_records_with_attachments())
