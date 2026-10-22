#!/usr/bin/env python3
"""Debug script for specific record FSP-PERM-202610080591 which has an attachment."""

import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://aca-prod.accela.com/ALLEGHENYCO"
RECORD_ID = "FSP-PERM-202610080591"


async def debug_record():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        page.set_default_timeout(10000)  # 10 second timeout
        
        # First, search to get the correct URL format
        print(f"Searching for record: {RECORD_ID}")
        await page.goto(f"{BASE_URL}/Cap/CapHome.aspx?module=EnvHealth&TabName=Home")
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        await asyncio.sleep(2)
        
        # Enter record number in search
        record_field = page.locator('#ctl00_PlaceHolderMain_generalSearchForm_txtGSPermitNumber')
        await record_field.fill(RECORD_ID)
        print("Filled record number, clicking search...")
        
        # Click search
        await page.locator('#ctl00_PlaceHolderMain_btnNewSearch').click()
        print("Clicked search, waiting for results...")
        
        # Wait for results with shorter timeout
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            print("Network idle timeout, continuing anyway...")
        await asyncio.sleep(3)
        
        # Check what we got
        page_text = await page.content()
        if "No matching records" in page_text:
            print("No matching records found message")
        
        # Check if we're already on the detail page (exact match search redirects)
        if RECORD_ID in page_text or "CapDetail" in page.url:
            print(f"Already on record detail page!")
        else:
            # Look for record links in search results
            record_links = await page.locator('a[href*="CapDetail"]').all()
            print(f"Found {len(record_links)} record links")
            
            if not record_links:
                print("No record links found. Saving search results page...")
                with open("/tmp/opencode/search_results.html", "w") as f:
                    f.write(page_text)
                print("Saved to /tmp/opencode/search_results.html")
                await browser.close()
                return
            
            # Get first record link
            href = await record_links[0].get_attribute("href")
            text = await record_links[0].text_content()
            print(f"First record: {text.strip() if text else 'no text'}")
            print(f"Link: {href}")
            
            # Navigate to record detail
            full_url = f"https://aca-prod.accela.com{href}" if href.startswith('/') else href
            print(f"Navigating to: {full_url}")
            await page.goto(full_url)
            
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                print("Network idle timeout on detail page, continuing...")
            await asyncio.sleep(2)
        
        print(f"\nRecord page URL: {page.url}")
        
        # Save full HTML
        html = await page.content()
        with open("/tmp/opencode/specific_record.html", "w") as f:
            f.write(html)
        print("Saved page HTML to /tmp/opencode/specific_record.html")
        
        # Look for all iframes
        print("\n=== IFRAMES ===")
        iframes = await page.locator('iframe').all()
        for i, iframe in enumerate(iframes):
            src = await iframe.get_attribute("src")
            iframe_id = await iframe.get_attribute("id")
            print(f"  [{i}] id={iframe_id} src={src[:80] if src else 'empty'}")
        
        # Check all frames
        print("\n=== PAGE FRAMES ===")
        for i, frame in enumerate(page.frames):
            url = frame.url
            print(f"  Frame {i}: {url[:100] if url else 'no url'}")
            
            if 'Attachment' in url or 'FileUpload' in url:
                print(f"\n  === ATTACHMENT FRAME CONTENT ===")
                
                # Get all elements in frame
                all_elements = await frame.locator('*').all()
                print(f"  Total elements: {len(all_elements)}")
                
                # Get all links
                links = await frame.locator('a').all()
                print(f"  Total links: {len(links)}")
                for link in links:
                    try:
                        href = await link.get_attribute("href")
                        text = await link.text_content()
                        link_id = await link.get_attribute("id")
                        onclick = await link.get_attribute("onclick")
                        if text and text.strip():
                            print(f"    id={link_id}")
                            print(f"    text='{text.strip()[:50]}'")
                            print(f"    href={href[:60] if href else 'None'}")
                            print(f"    onclick={onclick[:60] if onclick else 'None'}")
                            print()
                    except:
                        pass
                
                # Get table content
                tables = await frame.locator('table').all()
                print(f"  Tables: {len(tables)}")
                for j, table in enumerate(tables):
                    try:
                        table_id = await table.get_attribute("id")
                        text = await table.text_content()
                        print(f"    Table {j} id={table_id}")
                        print(f"    Content preview: {text[:200] if text else 'empty'}...")
                    except:
                        pass
                
                # Save frame HTML
                try:
                    frame_html = await frame.content()
                    with open(f"/tmp/opencode/attachment_frame.html", "w") as f:
                        f.write(frame_html)
                    print(f"  Saved frame HTML to /tmp/opencode/attachment_frame.html")
                except Exception as e:
                    print(f"  Error saving frame: {e}")
        
        # Also click the Attachments tab explicitly
        print("\n=== CLICKING ATTACHMENTS TAB ===")
        try:
            await page.evaluate('''() => {
                // Try multiple ways to activate attachments
                const tab = document.querySelector('a[href="#tab-attachments"], a[data-control="tab-attachments"]');
                if (tab) { 
                    tab.click();
                    console.log("Clicked tab");
                }
                
                // Show the tab content
                const content = document.getElementById('tab-attachments');
                if (content) {
                    content.style.display = 'block';
                }
                
                // Force iframe to load
                const iframe = document.getElementById('ctl00_PlaceHolderMain_attachmentEdit_iframeAttachmentList');
                if (iframe) {
                    const url = new URL(window.location.href);
                    const params = new URLSearchParams(url.search);
                    const newSrc = `/ALLEGHENYCO/FileUpload/AttachmentsList.aspx?module=EnvHealth&capID1=${params.get('capID1')}&capID2=${params.get('capID2')}&capID3=${params.get('capID3')}&agencyCode=ALLEGHENYCO&isdetail=True`;
                    if (!iframe.src || iframe.src === '' || iframe.src === 'about:blank') {
                        iframe.src = newSrc;
                    }
                    console.log("Set iframe src to: " + iframe.src);
                }
            }''')
            await asyncio.sleep(3)
            print("Activated attachments tab")
        except Exception as e:
            print(f"Error activating tab: {e}")
        
        # Check frames again after tab click
        print("\n=== FRAMES AFTER TAB CLICK ===")
        for i, frame in enumerate(page.frames):
            url = frame.url
            if url and 'about:' not in url and url != page.url:
                print(f"  Frame {i}: {url[:100]}")
                
                # Look for file links
                file_links = await frame.locator('a[id*="lnkFileName"], a[href*=".pdf"], a[href*="FileViewer"], a[href*="Download"]').all()
                print(f"    File links found: {len(file_links)}")
                
                for link in file_links:
                    try:
                        href = await link.get_attribute("href")
                        text = await link.text_content()
                        link_id = await link.get_attribute("id")
                        print(f"      {link_id}: '{text}' -> {href}")
                    except:
                        pass
                
                # Check for table rows (attachments are in a grid)
                rows = await frame.locator('tr.ACA_TabRow_Odd, tr.ACA_TabRow_Even, tr[class*="Row"]').all()
                print(f"    Data rows: {len(rows)}")
                for row in rows[:5]:
                    try:
                        text = await row.text_content()
                        print(f"      Row: {text[:100] if text else 'empty'}")
                    except:
                        pass
        
        await browser.close()
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(debug_record())
