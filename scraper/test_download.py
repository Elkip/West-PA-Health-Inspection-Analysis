#!/usr/bin/env python3
"""Test download of a specific record's attachment."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://aca-prod.accela.com/ALLEGHENYCO"
RECORD_ID = "FSP-PERM-202610080591"
OUTPUT_DIR = Path("/tmp/opencode/test_downloads")


async def test_download():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True
        )
        page = await context.new_page()
        page.set_default_timeout(15000)
        
        # Search for record
        print(f"Searching for {RECORD_ID}...")
        await page.goto(f"{BASE_URL}/Cap/CapHome.aspx?module=EnvHealth&TabName=Home")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(1)
        
        await page.fill('#ctl00_PlaceHolderMain_generalSearchForm_txtGSPermitNumber', RECORD_ID)
        await page.click('#ctl00_PlaceHolderMain_btnNewSearch')
        
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass
        await asyncio.sleep(2)
        
        print(f"On page: {page.url}")
        
        # Activate attachments tab
        print("Activating attachments tab...")
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
        
        # Check iframe src
        iframe_src = await page.evaluate('''() => {
            const iframe = document.getElementById('ctl00_PlaceHolderMain_attachmentEdit_iframeAttachmentList');
            return iframe ? iframe.src : 'not found';
        }''')
        print(f"Iframe src: {iframe_src}")
        
        # Wait a bit more and check frames
        await asyncio.sleep(2)
        
        # Find attachment frame
        print(f"Checking {len(page.frames)} frames...")
        attachment_frame = None
        for i, frame in enumerate(page.frames):
            print(f"  Frame {i}: {frame.url[:80] if frame.url else 'empty'}")
            if frame.url and ('AttachmentsList' in frame.url or 'FileUpload' in frame.url):
                attachment_frame = frame
                print(f"  -> This is the attachment frame!")
        
        if not attachment_frame:
            print("Could not find attachment frame!")
            print("Trying to manually set iframe src...")
            
            # Try setting src directly
            await page.evaluate('''() => {
                const iframe = document.getElementById('ctl00_PlaceHolderMain_attachmentEdit_iframeAttachmentList');
                if (iframe) {
                    const url = new URL(window.location.href);
                    const params = new URLSearchParams(url.search);
                    iframe.src = '/ALLEGHENYCO/FileUpload/AttachmentsList.aspx?module=EnvHealth&capID1=' + params.get('capID1') + '&capID2=' + params.get('capID2') + '&capID3=' + params.get('capID3') + '&agencyCode=ALLEGHENYCO&isdetail=True';
                    iframe.style.height = '500px';
                    console.log('Set iframe src to: ' + iframe.src);
                }
            }''')
            await asyncio.sleep(3)
            
            # Check frames again
            print(f"After manual src set, checking {len(page.frames)} frames...")
            for i, frame in enumerate(page.frames):
                url = frame.url if frame.url else 'empty'
                print(f"  Frame {i}: {url[:80]}")
                if 'AttachmentsList' in url or 'FileUpload' in url:
                    attachment_frame = frame
                    print(f"  -> Found attachment frame!")
        
        if not attachment_frame:
            print("Still could not find attachment frame!")
            await browser.close()
            return
        
        # Find download link
        links = await attachment_frame.locator('a[id*="lnkFileName"]').all()
        print(f"Found {len(links)} file links")
        
        if not links:
            print("No file links found!")
            await browser.close()
            return
        
        link = links[0]
        link_id = await link.get_attribute("id")
        file_name = await link.text_content()
        print(f"Attempting to download: {file_name}")
        print(f"Link ID: {link_id}")
        
        output_path = OUTPUT_DIR / file_name.strip()
        
        # Try to download by clicking the link
        print("Clicking download link...")
        
        try:
            # Method 1: Use context download event
            async with context.expect_event('download', timeout=30000) as download_info:
                await attachment_frame.click(f'#{link_id}')
            
            download = await download_info.value
            print(f"Download started: {download.suggested_filename}")
            await download.save_as(output_path)
            print(f"✓ Saved to: {output_path}")
            
        except PlaywrightTimeout as e:
            print(f"Download timeout: {e}")
            
            # Method 2: Check if file opened in new tab/window
            print("Checking for new pages...")
            pages = context.pages
            print(f"Open pages: {len(pages)}")
            for i, p in enumerate(pages):
                print(f"  Page {i}: {p.url[:80]}")
            
        except Exception as e:
            print(f"Download error: {e}")
        
        # Check if file was downloaded
        if output_path.exists():
            print(f"✓ File exists: {output_path} ({output_path.stat().st_size} bytes)")
        else:
            print("✗ File was not downloaded")
            
            # Try alternative: execute the postback manually
            print("\nTrying alternative download method...")
            try:
                # Get the onclick/href and execute it
                onclick = await link.get_attribute("onclick")
                href = await link.get_attribute("href")
                print(f"  onclick: {onclick}")
                print(f"  href: {href}")
                
                # The href is javascript:__doPostBack('attachmentList$gdvAttachmentList$ctl02$lnkFileName','')
                # We need to execute this in the iframe context
                
            except Exception as e:
                print(f"  Error: {e}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_download())
