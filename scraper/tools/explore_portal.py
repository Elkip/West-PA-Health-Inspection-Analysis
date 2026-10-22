#!/usr/bin/env python3
"""
Interactive exploration script for the Allegheny County Accela portal.

Run this script to open a browser and manually navigate the portal,
while also extracting useful information about the page structure.

Usage: python explore_portal.py
"""

import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://aca-prod.accela.com/ALLEGHENYCO"
SEARCH_URL = f"{BASE_URL}/Cap/CapHome.aspx?module=EnvHealth&TabName=Home"


async def explore():
    """Open browser for manual exploration with some helper functions."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print("=" * 60)
        print("ACCELA PORTAL EXPLORER")
        print("=" * 60)
        print(f"\nNavigating to: {SEARCH_URL}")
        
        await page.goto(SEARCH_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Extract useful information about the page
        print("\n--- FORM ELEMENTS ---\n")
        
        # Find all select elements (dropdowns)
        selects = await page.locator('select').all()
        print(f"Found {len(selects)} dropdown menus:")
        for select in selects[:10]:  # Limit to first 10
            try:
                id_attr = await select.get_attribute('id')
                name_attr = await select.get_attribute('name')
                if id_attr and 'GS' in id_attr:  # General Search fields
                    options = await select.locator('option').all_text_contents()
                    print(f"\n  ID: {id_attr}")
                    print(f"  Options: {options[:10]}{'...' if len(options) > 10 else ''}")
            except:
                pass
        
        # Find all input fields
        inputs = await page.locator('input[type="text"]').all()
        print(f"\n\nFound {len(inputs)} text input fields:")
        for inp in inputs[:15]:
            try:
                id_attr = await inp.get_attribute('id')
                name_attr = await inp.get_attribute('name')
                if id_attr and 'GS' in id_attr:
                    print(f"  ID: {id_attr}")
            except:
                pass
        
        # Find search buttons
        buttons = await page.locator('input[type="submit"], a[id*="btn"], input[id*="btn"]').all()
        print(f"\n\nFound {len(buttons)} buttons:")
        for btn in buttons[:10]:
            try:
                id_attr = await btn.get_attribute('id')
                value = await btn.get_attribute('value')
                text = await btn.text_content()
                print(f"  ID: {id_attr}, Value: {value}, Text: {text}")
            except:
                pass
        
        print("\n" + "=" * 60)
        print("BROWSER IS NOW OPEN FOR MANUAL EXPLORATION")
        print("=" * 60)
        print("\nTips:")
        print("1. Use browser DevTools (F12) to inspect elements")
        print("2. Try searching with different criteria")
        print("3. Click on a record to see its detail page structure")
        print("4. Look for attachment/document sections")
        print("\nPress Ctrl+C to close the browser and exit.")
        
        try:
            # Keep browser open until user closes it
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nClosing browser...")
        finally:
            await browser.close()


async def extract_record_type_options():
    """Extract all available record types from the dropdown."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(SEARCH_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Find the record type dropdown
        type_select = page.locator('#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType')
        
        if await type_select.count() > 0:
            options = await type_select.locator('option').all()
            print("Available Record Types:")
            print("-" * 40)
            for opt in options:
                value = await opt.get_attribute('value')
                text = await opt.text_content()
                if text and text.strip() != '--Select--':
                    print(f"  {text.strip()}")
        
        await browser.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--types":
        asyncio.run(extract_record_type_options())
    else:
        asyncio.run(explore())
