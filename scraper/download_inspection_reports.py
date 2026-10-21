#!/usr/bin/env python3
"""
Download inspection reports directly from the ACHD Oracle Reports server.

Encounter IDs follow the pattern: YYYYMMDDNNNN
where NNNN is a sequential number (0001, 0002, etc.) for inspections on that day.

This script enumerates possible encounter IDs and downloads PDFs for valid inspections.
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
import json

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Configuration
REPORT_BASE_URL = "https://appsrv.alleghenycounty.us/reports/rwservlet"
REPORT_PARAMS = "food_rep_insp&P_ENCOUNTER={encounter}"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "inspection_reports"
METADATA_FILE = OUTPUT_DIR / "downloaded_reports.json"

# Date range 
# WPRDC data ends around July 31, 2025
# ACHD switched to Accela on August 11, 2025
# Reports from Aug 1-10 are in the Oracle system
# After Aug 10, reports may be in Accela differently (uncertain)
START_DATE = datetime(2025, 8, 1)
END_DATE = datetime.now()  # Will stop finding reports after Aug ~10

# Maximum encounters to check per day (most days have < 100 inspections)
MAX_ENCOUNTERS_PER_DAY = 150


async def download_single_report(context, encounter_id: str, output_path: Path) -> bool:
    """
    Download a single inspection report PDF.
    Returns True if successful, False otherwise.
    """
    url = f"{REPORT_BASE_URL}?{REPORT_PARAMS.format(encounter=encounter_id)}"
    
    download_page = await context.new_page()
    try:
        # The server returns a PDF directly, which triggers a download
        async with download_page.expect_download(timeout=30000) as download_info:
            await download_page.goto(url)
        
        download = await download_info.value
        await download.save_as(output_path)
        return True
        
    except Exception as e:
        error_msg = str(e)
        # "Download is starting" is actually success for our purposes
        if "Download is starting" in error_msg:
            # The download started but we need to handle it differently
            try:
                # Try direct request
                response = await download_page.request.get(url)
                if response.ok:
                    content = await response.body()
                    if content[:4] == b'%PDF':
                        output_path.write_bytes(content)
                        return True
            except:
                pass
        
        # Check if it's an error page (no data found)
        try:
            page_content = await download_page.content()
            if "REP-771" in page_content or "no data found" in page_content.lower():
                return False
        except:
            pass
            
        return False
    finally:
        await download_page.close()


async def scan_date(context, date: datetime, existing_encounters: set) -> list:
    """Scan a single date for valid inspection encounters."""
    date_str = date.strftime("%Y%m%d")
    found_reports = []
    consecutive_misses = 0
    
    print(f"  Scanning {date.strftime('%Y-%m-%d')}...", end="", flush=True)
    
    for seq in range(1, MAX_ENCOUNTERS_PER_DAY + 1):
        encounter_id = f"{date_str}{seq:04d}"
        
        # Skip already downloaded
        if encounter_id in existing_encounters:
            consecutive_misses = 0
            continue
        
        # Prepare output path
        output_path = OUTPUT_DIR / f"{date.year}" / f"{date.strftime('%Y%m')}" / f"inspection_{encounter_id}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_path.exists():
            # Already downloaded
            consecutive_misses = 0
            continue
        
        # Try to download
        success = await download_single_report(context, encounter_id, output_path)
        
        if success:
            consecutive_misses = 0
            found_reports.append({
                "encounter": encounter_id,
                "date": date.isoformat(),
                "file": str(output_path)
            })
            print(".", end="", flush=True)
        else:
            consecutive_misses += 1
            
            # Stop after many consecutive misses (likely no more inspections that day)
            if consecutive_misses >= 20:
                break
        
        # Small delay to be respectful to the server
        await asyncio.sleep(0.2)
    
    print(f" Found {len(found_reports)}")
    return found_reports


async def main():
    """Main scanning routine."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing metadata
    existing_encounters = set()
    if METADATA_FILE.exists():
        with open(METADATA_FILE) as f:
            metadata = json.load(f)
            existing_encounters = set(r["encounter"] for r in metadata.get("reports", []))
    else:
        metadata = {"reports": [], "last_scan": None}
    
    print(f"Starting scan from {START_DATE.date()} to {END_DATE.date()}")
    print(f"Already have {len(existing_encounters)} encounters downloaded")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)
        
        try:
            current = START_DATE
            all_reports = metadata.get("reports", [])
            
            while current <= END_DATE:
                # Scan all days (inspections happen on weekends too)
                day_reports = await scan_date(context, current, existing_encounters)
                all_reports.extend(day_reports)
                
                # Update existing set
                for r in day_reports:
                    existing_encounters.add(r["encounter"])
                
                # Save after each day
                metadata["reports"] = all_reports
                metadata["last_scan"] = current.isoformat()
                with open(METADATA_FILE, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                current += timedelta(days=1)
                
        finally:
            await browser.close()
    
    print(f"\nScan complete!")
    print(f"Total reports found: {len(metadata['reports'])}")
    print(f"Reports saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
