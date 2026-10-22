#!/usr/bin/env python3
"""Debug script to explore record detail page completely."""

import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://aca-prod.accela.com/ALLEGHENYCO"


async def explore_record_fully():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=50)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print("Searching for Permanent Food Facility Permits...")
        await page.goto(f"{BASE_URL}/Cap/CapHome.aspx?module=EnvHealth&TabName=Home")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Set date range - use wider range
        await page.locator('#ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate').fill("08/11/2025")
        await page.locator('#ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate').fill("08/31/2025")
        
        # Select Permanent Food Facility Permit
        type_select = page.locator('#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType')
        await type_select.select_option(label="Permanent Food Facility Permit")
        await asyncio.sleep(1)
        
        # Search
        await page.locator('#ctl00_PlaceHolderMain_btnNewSearch').click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        
        # Get first record link
        first_link = page.locator('a[href*="CapDetail"]').first
        href = await first_link.get_attribute("href")
        text = await first_link.text_content()
        print(f"First record: {text.strip() if text else 'unknown'}")
        
        # Navigate to record
        await page.goto(f"https://aca-prod.accela.com{href}")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Save the full page HTML
        html = await page.content()
        with open("/tmp/opencode/record_full.html", "w") as f:
            f.write(html)
        print("Full page HTML saved to /tmp/opencode/record_full.html")
        
        # Look at all clickable tabs/menu items
        print("\n--- ALL MENU/TAB ITEMS ---")
        menu_items = await page.locator('a[data-control], li a, .record-menu a, nav a').all()
        for item in menu_items[:30]:
            try:
                text = await item.text_content()
                data_ctrl = await item.get_attribute("data-control")
                href = await item.get_attribute("href")
                if text and text.strip():
                    print(f"  '{text.strip()[:30]}' data-control={data_ctrl} href={href[:40] if href else None}")
            except:
                pass
        
        # Click through all tabs and see what loads
        print("\n--- EXPLORING TABS ---")
        tab_controls = ['tab-RecordInfo', 'tab-RecordDetail', 'tab-attachments', 'tab-DocumentStatus']
        
        for tab_id in tab_controls:
            print(f"\n  Activating tab: {tab_id}")
            try:
                await page.evaluate(f'''() => {{
                    const content = document.getElementById('{tab_id}');
                    if (content) {{
                        content.style.display = 'block';
                        content.classList.add('active');
                    }}
                    const tab = document.querySelector('a[data-control="{tab_id}"]');
                    if (tab) tab.click();
                }}''')
                await asyncio.sleep(1)
                
                # Check what's in this tab
                tab_content = page.locator(f'#{tab_id}')
                if await tab_content.count() > 0:
                    links = await tab_content.locator('a[href]').all()
                    print(f"    Found {len(links)} links in {tab_id}")
                    for link in links[:10]:
                        href = await link.get_attribute("href")
                        text = await link.text_content()
                        if href and 'javascript:' not in href:
                            print(f"      '{text.strip() if text else ''}' -> {href[:60]}")
            except Exception as e:
                print(f"    Error: {e}")
        
        # Check all iframes
        print("\n--- ALL IFRAMES ---")
        iframes = await page.locator('iframe').all()
        for i, iframe in enumerate(iframes):
            src = await iframe.get_attribute("src")
            iframe_id = await iframe.get_attribute("id")
            print(f"  iframe {i}: id={iframe_id} src={src[:80] if src else 'empty'}")
        
        # Check page frames
        print("\n--- PAGE FRAMES ---")
        for i, frame in enumerate(page.frames):
            print(f"  Frame {i}: {frame.url[:100] if frame.url else 'no url'}")
            if frame.url and frame.url != page.url and 'about:' not in frame.url:
                # Save frame content
                try:
                    frame_html = await frame.content()
                    with open(f"/tmp/opencode/frame_{i}.html", "w") as f:
                        f.write(frame_html)
                    print(f"    Saved to /tmp/opencode/frame_{i}.html")
                    
                    # Look for any links in frame
                    links = await frame.locator('a[href]').all()
                    print(f"    {len(links)} links in frame")
                    for link in links[:10]:
                        href = await link.get_attribute("href")
                        text = await link.text_content()
                        if href and 'javascript:__doPostBack' not in href:
                            print(f"      '{text.strip() if text else ''}' -> {href[:60]}")
                except Exception as e:
                    print(f"    Error getting frame content: {e}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(explore_record_fully())
