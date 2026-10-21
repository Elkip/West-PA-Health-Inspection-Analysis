#!/usr/bin/env python3
"""Debug script to find inspections and encounter IDs."""

import asyncio
import re
from playwright.async_api import async_playwright

BASE_URL = "https://aca-prod.accela.com/ALLEGHENYCO"


async def find_inspections():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=50)
        page = await browser.new_page()
        
        # Check what modules/record types are available
        print("=== Checking EnvHealth module ===")
        await page.goto(f"{BASE_URL}/Cap/CapHome.aspx?module=EnvHealth&TabName=Home")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Get all record types
        type_select = page.locator('#ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType')
        options = await type_select.locator('option').all_text_contents()
        print("Available record types in EnvHealth:")
        for opt in options:
            print(f"  - {opt}")
        
        # Look for any inspections-related records
        print("\n=== Searching for recent Food Facility records ===")
        
        await page.locator('#ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate').fill("08/11/2025")
        await page.locator('#ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate').fill("08/15/2025")
        await type_select.select_option(label="Permanent Food Facility Permit")
        await asyncio.sleep(1)
        
        await page.locator('#ctl00_PlaceHolderMain_btnNewSearch').click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        
        # Get record details
        records = await page.locator('a[href*="CapDetail"]').all()
        print(f"Found {len(records)} records")
        
        for i, record in enumerate(records[:3]):
            href = await record.get_attribute("href")
            text = await record.text_content()
            record_num = text.strip() if text else "unknown"
            print(f"\n--- Record {i+1}: {record_num} ---")
            
            # Navigate to record
            await page.goto(f"https://aca-prod.accela.com{href}")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # Look for inspection-related content
            page_text = await page.content()
            
            # Look for encounter patterns in the page
            encounter_pattern = r'P_ENCOUNTER=(\d+)|encounter["\s:=]+(\d{12,})'
            encounters = re.findall(encounter_pattern, page_text, re.IGNORECASE)
            if encounters:
                print(f"  Found encounter references: {encounters}")
            
            # Look for inspection links
            inspection_links = await page.locator('a[href*="inspection"], a[href*="Inspection"], a:has-text("Inspection")').all()
            print(f"  Found {len(inspection_links)} inspection-related links")
            for link in inspection_links[:5]:
                link_href = await link.get_attribute("href")
                link_text = await link.text_content()
                print(f"    '{link_text.strip() if link_text else ''}' -> {link_href[:80] if link_href else ''}")
            
            # Check for any report/PDF links
            report_links = await page.locator('a[href*="report"], a[href*="rwservlet"], a[href*=".pdf"]').all()
            print(f"  Found {len(report_links)} report-related links")
            for link in report_links[:5]:
                link_href = await link.get_attribute("href")
                link_text = await link.text_content()
                print(f"    '{link_text.strip() if link_text else ''}' -> {link_href[:80] if link_href else ''}")
            
            # Check the "IsToShowInspection" parameter in URL
            if "IsToShowInspection" in href:
                print("  URL has IsToShowInspection parameter")
            
            # Look for Related Records section
            related = await page.locator('text="Related Records", text="Inspections", text="Related"').all()
            print(f"  Found {len(related)} related/inspection sections")
        
        # Try adding IsToShowInspection=Y to URL
        print("\n=== Trying with IsToShowInspection=Y ===")
        first_record = await page.locator('a[href*="CapDetail"]').first.get_attribute("href")
        if first_record:
            inspection_url = f"https://aca-prod.accela.com{first_record}&IsToShowInspection=Y"
            print(f"Navigating to: {inspection_url}")
            await page.goto(inspection_url)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # Check for inspection data
            insp_content = await page.locator('[id*="inspection"], [id*="Inspection"], [class*="inspection"]').all()
            print(f"Found {len(insp_content)} inspection-related elements")
            
            # Save HTML for inspection
            html = await page.content()
            with open("/tmp/opencode/inspection_page.html", "w") as f:
                f.write(html)
            print("Saved inspection page to /tmp/opencode/inspection_page.html")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(find_inspections())
