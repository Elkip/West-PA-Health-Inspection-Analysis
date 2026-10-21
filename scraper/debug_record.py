#!/usr/bin/env python3
"""Debug script to explore a single record's structure."""

import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://aca-prod.accela.com/ALLEGHENYCO"
SEARCH_URL = f"{BASE_URL}/Cap/CapHome.aspx?module=EnvHealth&TabName=Home"


async def debug_record():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=50)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print("Navigating to search page...")
        await page.goto(SEARCH_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Set date range to find some records
        start_field = page.locator('#ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate')
        await start_field.clear()
        await start_field.fill("08/01/2025")
        
        end_field = page.locator('#ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate')
        await end_field.clear()
        await end_field.fill("08/31/2025")
        
        # Select Food Facility Permit type if available
        type_select = page.locator('#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType')
        if await type_select.count() > 0:
            options = await type_select.locator('option').all_text_contents()
            print(f"Available record types: {options[:15]}...")
            # Try to find "Permanent Food Facility Permit" specifically
            for opt in options:
                if 'permanent' in opt.lower() and 'food' in opt.lower():
                    print(f"Selecting: {opt}")
                    await type_select.select_option(label=opt)
                    await asyncio.sleep(1)
                    break
        
        # Click search
        await page.locator('#ctl00_PlaceHolderMain_btnNewSearch').click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        
        # Find and click first record link
        print("\n--- SEARCH RESULTS ---")
        all_links = await page.locator('a[href*="CapDetail"]').all()
        print(f"Found {len(all_links)} record links")
        
        if all_links:
            # Try multiple records to find one with attachments
            for record_idx, record_link in enumerate(all_links[:5]):
                href = await record_link.get_attribute("href")
                text = await record_link.text_content()
                print(f"\n=== Trying record {record_idx + 1}: {text.strip() if text else 'no text'} ===")
                
                # Navigate to record detail page  
                await page.goto(f"https://aca-prod.accela.com{href}")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            
            print("\n--- RECORD DETAIL PAGE ---")
            print(f"URL: {page.url}")
            
            # Look for ALL tabs/sections on the page
            print("\n--- TABS/SECTIONS ---")
            tabs = await page.locator('a[id*="Tab"], li a, .ACA_TabRow a, a[role="tab"]').all()
            for tab in tabs[:20]:
                try:
                    text = await tab.text_content()
                    id_attr = await tab.get_attribute("id")
                    href = await tab.get_attribute("href")
                    if text and text.strip():
                        print(f"  Tab: '{text.strip()}' | id={id_attr}")
                except:
                    pass
            
            # Look for section headers
            print("\n--- SECTION HEADERS ---")
            headers = await page.locator('h1, h2, h3, .ACA_Section_Title, [class*="section"], [class*="header"]').all()
            for h in headers[:15]:
                try:
                    text = await h.text_content()
                    if text and text.strip() and len(text.strip()) < 100:
                        print(f"  {text.strip()}")
                except:
                    pass
            
            # Look for anything with "attachment" or "document" in ID or class
            print("\n--- ATTACHMENT-RELATED ELEMENTS ---")
            att_elements = await page.locator('[id*="ttachment"], [id*="ocument"], [class*="ttachment"], [class*="ocument"]').all()
            for elem in att_elements[:20]:
                try:
                    tag = await elem.evaluate("el => el.tagName")
                    id_attr = await elem.get_attribute("id")
                    class_attr = await elem.get_attribute("class")
                    text = await elem.text_content()
                    text_preview = text[:100] if text else ""
                    print(f"  <{tag}> id={id_attr} class={class_attr}")
                    if text_preview.strip():
                        print(f"    text: {text_preview.strip()}")
                except:
                    pass
            
            # Look for tables that might contain attachments
            print("\n--- TABLES ---")
            tables = await page.locator('table[id]').all()
            for table in tables[:10]:
                try:
                    id_attr = await table.get_attribute("id")
                    print(f"  Table: {id_attr}")
                except:
                    pass
            
            # Look for any links that look like downloads
            print("\n--- DOWNLOAD-LIKE LINKS (main page) ---")
            download_links = await page.locator('a[href*="Download"], a[href*="File"], a[href*=".pdf"], a[href*="View"]').all()
            for link in download_links[:20]:
                try:
                    href = await link.get_attribute("href")
                    text = await link.text_content()
                    print(f"  '{text.strip() if text else 'no text'}' -> {href[:100] if href else 'no href'}")
                except:
                    pass
            
            # Click on Attachments tab to load iframe - use JavaScript since the tab may not be visible
            print("\n--- ACTIVATING ATTACHMENTS TAB ---")
            # Try to activate the tab via JavaScript
            try:
                # Method 1: Click the tab via JavaScript
                await page.evaluate('''() => {
                    const tab = document.querySelector('a[href="#tab-attachments"], a[data-control="tab-attachments"]');
                    if (tab) tab.click();
                    // Also try showing the tab content directly
                    const tabContent = document.getElementById('tab-attachments');
                    if (tabContent) tabContent.style.display = 'block';
                }''')
                await asyncio.sleep(2)
                
                # Method 2: Set iframe src directly if it's empty
                await page.evaluate('''() => {
                    const iframe = document.getElementById('ctl00_PlaceHolderMain_attachmentEdit_iframeAttachmentList');
                    if (iframe && (!iframe.src || iframe.src === '')) {
                        // Construct the attachment URL from the page's capID parameters
                        const urlParams = new URLSearchParams(window.location.search);
                        const capID1 = urlParams.get('capID1') || '';
                        const capID2 = urlParams.get('capID2') || '';
                        const capID3 = urlParams.get('capID3') || '';
                        const module = urlParams.get('Module') || 'EnvHealth';
                        iframe.src = `/ALLEGHENYCO/FileUpload/AttachmentsList.aspx?module=${module}&capID1=${capID1}&capID2=${capID2}&capID3=${capID3}&agencyCode=ALLEGHENYCO`;
                        iframe.style.height = '400px';
                        iframe.style.width = '100%';
                    }
                }''')
                await asyncio.sleep(3)  # Wait for iframe to load
                print("  Activated Attachments tab via JavaScript")
            except Exception as e:
                print(f"  Error activating tab: {e}")
            
            # Now check iframe content
            print("\n--- IFRAME CONTENT ---")
            iframe = page.frame_locator('#ctl00_PlaceHolderMain_attachmentEdit_iframeAttachmentList')
            count = 0
            
            # Check if iframe has content
            try:
                # Get all links in the iframe
                iframe_links = iframe.locator('a')
                count = await iframe_links.count()
                print(f"  Found {count} links in iframe")
                
                for i in range(min(count, 20)):
                    link = iframe_links.nth(i)
                    href = await link.get_attribute("href")
                    text = await link.text_content()
                    print(f"    [{i}] '{text.strip() if text else 'no text'}' -> {href[:80] if href else 'no href'}")
            except Exception as e:
                print(f"  Error accessing iframe via frame_locator: {e}")
            
            # Also try to get the iframe src
            iframe_elem = page.locator('#ctl00_PlaceHolderMain_attachmentEdit_iframeAttachmentList')
            src = await iframe_elem.get_attribute("src")
            print(f"\n  Iframe src: {src}")
            
            # Try to get frames directly - more reliable approach
            print("\n--- TRYING DIRECT FRAME ACCESS ---")
            try:
                frames = page.frames
                print(f"  Page has {len(frames)} frames:")
                for i, frame in enumerate(frames):
                    frame_url = frame.url if frame.url else 'no url'
                    print(f"    Frame {i}: {frame_url[:80]}")
                    if 'Attachment' in frame_url or 'FileUpload' in frame_url:
                        # This is our attachment frame
                        print(f"\n      --- ATTACHMENT FRAME CONTENT ---")
                        
                        # Look for actual file links (not header links)
                        file_links = await frame.locator('a[id*="lnkFileName"], a[href*="FileViewer"], a[href*="Download"]').all()
                        print(f"      Found {len(file_links)} file download links:")
                        for link in file_links[:15]:
                            href = await link.get_attribute("href")
                            text = await link.text_content()
                            link_id = await link.get_attribute("id")
                            print(f"        id={link_id} '{text.strip() if text else ''}' -> {href[:80] if href else ''}")
                        
                        # Also look at all table rows
                        rows = await frame.locator('table tr').all()
                        print(f"\n      Found {len(rows)} table rows")
                        
                        # Get all links and their hrefs for debugging
                        all_links = await frame.locator('a[href]').all()
                        print(f"\n      All links with href ({len(all_links)}):")
                        for link in all_links:
                            href = await link.get_attribute("href")
                            text = await link.text_content()
                            if href and 'javascript:__doPostBack' not in href:
                                print(f"        '{text.strip() if text else ''}' -> {href}")
            except Exception as e:
                print(f"  Error accessing frames: {e}")
            
            # Dump the page HTML to a file for inspection
            html = await page.content()
            with open("/tmp/opencode/record_page.html", "w") as f:
                f.write(html)
            print("\n--- Full HTML saved to /tmp/opencode/record_page.html ---")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_record())
