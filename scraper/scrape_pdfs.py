#!/usr/bin/env python3
"""
Scrape ACHD Food Safety Assessment Report PDFs from data/accela_downloads
into CSV files matching the historical inspections.csv and violations.csv schemas,
and optionally combine them with data/wprdc_inspections.csv and data/wprdc_violations.csv.

Usage:
    python3 scraper/scrape_pdfs.py
    python3 scraper/scrape_pdfs.py --combine
"""

import argparse
import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pypdf

DEFAULT_INPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "accela_downloads"
DEFAULT_INSPECTIONS_CSV = Path(__file__).resolve().parent.parent / "data" / "accela_inspections.csv"
DEFAULT_VIOLATIONS_CSV = Path(__file__).resolve().parent.parent / "data" / "accela_violations.csv"
DEFAULT_WPRDC_INSPECTIONS = Path(__file__).resolve().parent.parent / "data" / "wprdc_inspections.csv"
DEFAULT_WPRDC_VIOLATIONS = Path(__file__).resolve().parent.parent / "data" / "wprdc_violations.csv"
DEFAULT_COMBINED_INSPECTIONS = Path(__file__).resolve().parent.parent / "data" / "inspections.csv"
DEFAULT_COMBINED_VIOLATIONS = Path(__file__).resolve().parent.parent / "data" / "violations.csv"

INSPECTIONS_COLUMNS = [
    "_id",
    "encounter",
    "id",
    "placard_st",
    "placard_desc",
    "facility_name",
    "bus_st_date",
    "category_cd",
    "description",
    "num",
    "street",
    "city",
    "state",
    "zip",
    "inspect_dt",
    "start_time",
    "end_time",
    "municipal",
    "ispt_purpose",
    "abrv",
    "purpose",
    "reispt_cd",
    "reispt_dt",
    "status",
]

VIOLATIONS_COLUMNS = [
    "_id",
    "encounter",
    "id",
    "placard_st",
    "facility_name",
    "bus_st_date",
    "description",
    "description_new",
    "num",
    "street",
    "city",
    "state",
    "zip",
    "inspect_dt",
    "start_time",
    "end_time",
    "municipal",
    "rating",
    "low",
    "medium",
    "high",
    "url",
]

# Column X-coordinate centers on Page 1 for the new Accela template (has "Imminent")
NEW_COLS: Dict[float, str] = {
    316.7: "D",
    338.8: "S",
    358.3: "NA",
    378.9: "NO",
    400.6: "V",
    437.4: "High",
    468.6: "Med",
    495.1: "Low",
    536.0: "Imminent",
}

# Column X-coordinate centers on Page 1 for the historical FPREP template
OLD_COLS: Dict[float, str] = {
    357.0: "D",
    384.3: "S",
    411.3: "NO",
    438.3: "NA",
    465.3: "V",
    496.8: "High",
    526.1: "Med",
    557.5: "Low",
}

# Canonical 33 assessment categories matching violations.csv description_new
CATEGORIES: Dict[int, str] = {
    1: "Food Source/Condition",
    2: "Cooking Temperatures",
    3: "Consumer Advisory",
    4: "Reheating Temperatures",
    5: "Cooling Food",
    6: "Hot Holding Temperatures",
    7: "Cold Holding Temperatures",
    8: "Facilities to Maintain Temperature",
    9: "Date Marking of Food",
    10: "Probe-Type Thermometers",
    11: "Cross-Contamination Prevention",
    12: "Employee Health",
    13: "Employee Personal Hygiene",
    14: "Cleaning and Sanitization",
    15: "Water Supply",
    16: "Waste Water Disposal",
    17: "Plumbing",
    18: "Handwashing Facilities",
    19: "Pest Management",
    20: "Toxic Items",
    21: "Certified Food Protection Manager",
    22: "Demonstration of Knowledge",
    23: "Contamination Prevention - Food, Utensils and Equipment",
    24: "Fabrication, Design, Installation and Maintenance",
    25: "Toilet Room",
    26: "Garbage and Refuse",
    27: "Floors",
    28: "Walls and ceilings",
    29: "Lighting",
    30: "Ventilation",
    31: "Dressing rooms and Locker rooms",
    32: "General Premises",
    33: "Administrative",
}

PLACARD_MAP: Dict[str, Tuple[str, str]] = {
    "inspected & permitted": ("1", "Inspected & Permitted"),
    "consumer alert": ("2", "Consumer Alert"),
    "ordered to close": ("3", "Ordered To Close"),
    "inspected/permit denied": ("4", "Inspected/Permit denied"),
    "inspected / permit denied": ("4", "Inspected/Permit denied"),
    "closure/unpaid fees": ("5", "Closure/Unpaid Fees"),
    "closure/imminent hazard": ("6", "Closure/Imminent Hazard"),
    "closure/no entry": ("7", "Closure/No Entry"),
    "not selected": ("0", "Not Selected"),
}

PURPOSE_MAP: Dict[str, Tuple[str, str, str]] = {
    "initial": ("1", "Ini", "Initial"),
    "comprehensive": ("1", "Comp", "Comprehensive"),
    "reinspection": ("2", "Reispt", "Reinspection"),
    "new facility": ("4", "New Fac", "New Facility"),
    "initial, new fac": ("5", "Ini, New Fac", "Initial, New Facility"),
    "initial, new facility": ("5", "Ini, New Fac", "Initial, New Facility"),
    "service request": ("7", "Srv Req", "Service Request"),
    "service reques": ("7", "Srv Req", "Service Request"),
    "complaint": ("8", "Comp", "Complaint"),
    "complaint investigation": ("8", "Comp", "Complaint"),
    "initial,srv req": ("9", "Ini,Srv Req", "Initial, Service Request"),
    "initial, service": ("9", "Ini,Srv Req", "Initial, Service Request"),
    "remodel": ("32", "Remod", "Remodel"),
    "consultation": ("50", "Cnslt", "Consultation"),
    "administrative action": ("51", "Admin", "Administrative Action"),
    "administrative act": ("51", "Admin", "Administrative Action"),
    "initial, complaint": ("52", "Ini, Comp", "Initial, Complaint"),
    "initial, complai": ("52", "Ini, Comp", "Initial, Complaint"),
    "partial reinspection": ("57", "Part. Reinsp", "Partial ReInspection"),
    "partial reinspe": ("57", "Part. Reinsp", "Partial ReInspection"),
    "covid-19": ("58", "Covid-19", "COVID-19"),
    "covid-19, initi": ("59", "Covid-19, Ini", "COVID-19, Initial Inspection"),
    "covid-19, initial in": ("59", "Covid-19, Ini", "COVID-19, Initial Inspection"),
    "covid-19, initial inspection": ("59", "Covid-19, Ini", "COVID-19, Initial Inspection"),
    "covid-19 assessment": ("63", "Covid-19 Assessment", "COVID-19 Assessment"),
}


def extract_page_items(page) -> List[Tuple[float, float, str]]:
    """Extract (x, y, text) items from a pypdf Page."""
    items: List[Tuple[float, float, str]] = []

    def visitor(text, cm, tm, font_dict, font_size):
        if text and text.strip():
            items.append((round(float(tm[4]), 1), round(float(tm[5]), 1), text.strip()))

    page.extract_text(visitor_text=visitor)
    return items


def map_column(x: float, cols: Dict[float, str], tolerance: float = 10.0) -> Optional[str]:
    """Map an X coordinate to the nearest table column name."""
    best_col: Optional[str] = None
    best_dist = tolerance
    for col_x, name in cols.items():
        dist = abs(x - col_x)
        if dist < best_dist:
            best_dist = dist
            best_col = name
    return best_col


def parse_header_fields(
    items: List[Tuple[float, float, str]], min_y: float = 590.0, max_y: float = 690.0
) -> Dict[str, str]:
    """Parse label: value fields in the header block using spatial coordinates."""
    ignore = {
        "Food Safety Assessment Categories",
        "Assessment Status",
        "Violation Risk",
        "I N S P E C T I O N    D E T A I L S",
        "Inspection Details",
    }
    labels: List[Tuple[float, float, str]] = []
    values: List[Tuple[float, float, str]] = []

    for x, y, text in items:
        if min_y <= y <= max_y and text not in ignore:
            if text.endswith(":"):
                labels.append((x, y, text[:-1].strip()))
            else:
                values.append((x, y, text))

    assigned: Dict[str, List[str]] = {label_name: [] for _, _, label_name in labels}

    for vx, vy, vtext in sorted(values, key=lambda item: (-item[1], item[0])):
        candidates: List[Tuple[float, str]] = []
        for lx, ly, lname in labels:
            if vx < lx + 10:
                continue
            if not (-3.0 <= ly - vy <= 16.0):
                continue
            # Ensure no other label is on the same horizontal row between lx and vx
            if any(abs(ly2 - ly) < 5.0 and lx < lx2 <= vx for lx2, ly2, _ in labels):
                continue
            # If wrapped onto the next line, ensure no other label sits at that line in the same column
            if ly - vy > 3.0 and any(abs(ly2 - vy) < 3.0 and abs(lx2 - lx) < 30.0 for lx2, ly2, _ in labels):
                continue
            dist = abs(ly - vy) * 10.0 + (vx - lx) * 0.1
            candidates.append((dist, lname))

        if candidates:
            best_label = min(candidates)[1]
            assigned[best_label].append(vtext)

    result = {k: " ".join(v).strip() for k, v in assigned.items()}

    # Clean up wrapped "Pre-Operational Inspection" or "Complaint Investigation" spillover into Permit Exp. Date
    purpose = result.get("Purpose", "")
    permit_exp = result.get("Permit Exp. Date", "")
    if purpose == "Pre-Operational" and permit_exp.startswith("Inspection"):
        result["Purpose"] = "Pre-Operational Inspection"
        result["Permit Exp. Date"] = permit_exp[len("Inspection") :].strip()

    return result


def format_date(dt_str: str) -> str:
    """Normalize date strings (M/D/YYYY, MM/DD/YYYY, YYYY-MM-DD) to YYYY-MM-DD."""
    if not dt_str:
        return ""
    dt_str = dt_str.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(dt_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return dt_str


def format_time(tm_str: str) -> str:
    """Normalize time strings (e.g. '3:45 PM', '03:20:00 PM') to HH:MM:SS."""
    if not tm_str:
        return ""
    tm_str = tm_str.strip()
    for fmt in ("%I:%M %p", "%I:%M:%S %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(tm_str, fmt).strftime("%H:%M:%S")
        except ValueError:
            pass
    return tm_str


def split_address(address: str) -> Tuple[str, str]:
    """Split street address into (num, street)."""
    address = address.strip()
    if not address:
        return "", ""
    match = re.match(r"^(\d+[A-Za-z]?(?:-\d+[A-Za-z]?)?)\s+(.*)$", address)
    if match:
        return match.group(1), match.group(2).strip()
    return "", address


def parse_category_code(cat_str: str) -> Tuple[str, str]:
    """Parse '211-Restaurant w/o Liquor' (or comma-separated list) into (category_cd, description)."""
    if not cat_str:
        return "", ""
    first_part = cat_str.split(",")[0].strip()
    match = re.match(r"^(\d+)\s*-\s*(.*)$", first_part)
    if not match:
        return "", first_part
    code = match.group(1).strip()
    desc = match.group(2).strip()
    desc = re.sub(r"\bw/o\b", "without", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\bw/\s*", "with ", desc, flags=re.IGNORECASE)
    return code, desc


def normalize_municipality(muni: str) -> str:
    """Normalize municipality names to align with historical conventions."""
    if not muni:
        return ""
    muni = " ".join(muni.split())
    ward_match = re.match(r"^CITY OF PITTSBURGH\s*-\s*WARD\s*(\d+)$", muni, flags=re.IGNORECASE)
    if ward_match:
        ward = int(ward_match.group(1))
        return f"Pittsburgh-{100 + ward}"
    # Title-case ALL-CAPS municipality names while stripping trailing Borough/Township/Municipality if desired,
    # or keep clean title case.
    if muni.isupper():
        muni = re.sub(r"\s+(BOROUGH|TOWNSHIP|MUNICIPALITY)$", "", muni, flags=re.IGNORECASE)
        return muni.title()
    return muni


def parse_purpose(purpose_raw: str) -> Tuple[str, str, str]:
    """Map PDF purpose string to (ispt_purpose, abrv, purpose)."""
    if not purpose_raw:
        return "", "", ""
    key = purpose_raw.strip().lower()
    if key in PURPOSE_MAP:
        return PURPOSE_MAP[key]
    return "", purpose_raw.strip(), purpose_raw.strip()


def parse_placard(placard_raw: str) -> Tuple[str, str]:
    """Map PDF placarding string to (placard_st, placard_desc)."""
    if not placard_raw:
        return "", ""
    key = placard_raw.strip().lower()
    if key in PLACARD_MAP:
        return PLACARD_MAP[key]
    return "", placard_raw.strip()


def parse_reinspection_code(reinsp_raw: str) -> str:
    """Map Re-Inspection string to reispt_cd."""
    if not reinsp_raw:
        return ""
    low = reinsp_raw.strip().lower()
    if low.startswith("yes"):
        return "1"
    if low.startswith("no"):
        return "2"
    return ""


def parse_pdf(pdf_path: Path, root_dir: Path) -> Optional[Tuple[Dict[str, str], List[Dict[str, str]], Set[Tuple[int, Tuple[str, ...]]]]]:
    """
    Parse a single Food Safety Assessment Report PDF.
    Returns (inspection_dict, violation_dicts, frozen_marks_set) or None if not a valid inspection report.
    """
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception:
        return None

    if len(reader.pages) < 2:
        return None

    items1 = extract_page_items(reader.pages[0])
    full_text1 = " ".join(t for _, _, t in items1)
    if "Food Safety Assessment" not in full_text1 and "FOOD SAFETY ASSESSMENT" not in full_text1:
        return None

    is_new = any(t == "Imminent" for _, _, t in items1)
    cols = NEW_COLS if is_new else OLD_COLS

    # Locate category rows 1..33 on Page 1
    row_ys: Dict[int, float] = {}
    for x, y, text in items1:
        if 45.0 < x < 65.0 and text.isdigit() and 1 <= int(text) <= 33 and 75.0 < y < 580.0:
            row_ys[int(text)] = y

    if len(row_ys) != 33:
        return None

    # Map X marks on Page 1 to (row_number, column_name)
    row_marks: Dict[int, Set[str]] = {i: set() for i in range(1, 34)}
    for x, y, text in items1:
        if text in ("X", "x") and x > 300.0:
            best_r = min(row_ys.keys(), key=lambda r_num: abs(row_ys[r_num] - y))
            if abs(row_ys[best_r] - y) < 6.0:
                col_name = map_column(x, cols)
                if col_name:
                    row_marks[best_r].add(col_name)

    fields1 = parse_header_fields(items1, min_y=590.0, max_y=690.0)
    items2 = extract_page_items(reader.pages[1])
    fields2 = parse_header_fields(items2, min_y=614.0, max_y=670.0)

    client_id = fields1.get("Client ID", "").strip()
    if not client_id:
        client_id = pdf_path.parent.name

    facility_name = fields1.get("Client Name", "").strip()
    if not facility_name:
        facility_name = fields2.get("Contact", "").strip() or client_id

    # Extract 12-digit encounter ID from bottom-right of Page 1
    bottom_items = [t for x, y, t in items1 if y < 40.0 and x > 450.0]
    enc_match = re.search(r"(20\d{10})", "".join(bottom_items))
    encounter = enc_match.group(1) if enc_match else ""

    # Fallback encounter ID from filename timestamp if blank in PDF
    if not encounter:
        fname_match = re.search(r"(20\d{6})_(\d{6})", pdf_path.name)
        if fname_match:
            encounter = f"{fname_match.group(1)}{fname_match.group(2)}"
        else:
            encounter = pdf_path.stem

    inspect_dt = format_date(fields1.get("Inspection Date", ""))
    if not inspect_dt:
        if len(encounter) >= 8 and encounter[:8].isdigit():
            inspect_dt = f"{encounter[:4]}-{encounter[4:6]}-{encounter[6:8]}"

    num, street = split_address(fields1.get("Address", ""))
    city = fields1.get("City", "").strip()
    if city.isupper():
        city = city.title()
    state = fields1.get("State", "PA").strip() or "PA"
    zip_code = fields1.get("Zip", "").strip()
    municipal = normalize_municipality(fields1.get("Municipality", ""))

    category_cd, category_desc = parse_category_code(fields1.get("Category Code", ""))
    placard_st, placard_desc = parse_placard(fields2.get("Placarding", ""))
    ispt_purpose, abrv, purpose = parse_purpose(fields1.get("Purpose", ""))

    reinsp_raw = fields1.get("Re-Inspection", fields1.get("Re- Inspection", ""))
    reispt_cd = parse_reinspection_code(reinsp_raw)
    reinsp_dt_raw = fields1.get("Re-Inspection Date", fields1.get("Re- Inspection Date", ""))
    reispt_dt = format_date(reinsp_dt_raw)

    start_time = format_time(fields2.get("Start Time", ""))
    end_time = format_time(fields2.get("End Time", ""))

    try:
        rel_path = pdf_path.relative_to(root_dir.parent.parent).as_posix()
    except ValueError:
        rel_path = str(pdf_path)

    if pdf_path.name.startswith("FPREP_") and len(encounter) == 12:
        report_url = f"https://appsrv.alleghenycounty.us/reports/rwservlet?food_rep_insp&P_ENCOUNTER={encounter}"
    else:
        report_url = rel_path

    inspection_row = {
        "_id": "",
        "encounter": encounter,
        "id": client_id,
        "placard_st": placard_st,
        "placard_desc": placard_desc,
        "facility_name": facility_name,
        "bus_st_date": "",
        "category_cd": category_cd,
        "description": category_desc,
        "num": num,
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "inspect_dt": inspect_dt,
        "start_time": start_time,
        "end_time": end_time,
        "municipal": municipal,
        "ispt_purpose": ispt_purpose,
        "abrv": abrv,
        "purpose": purpose,
        "reispt_cd": reispt_cd,
        "reispt_dt": reispt_dt,
        "status": "",
    }

    violation_rows: List[Dict[str, str]] = []
    for r_num in range(1, 34):
        marks = row_marks[r_num]
        has_v = "V" in marks
        has_risk = any(m in marks for m in ("High", "Med", "Low", "Imminent"))
        if not has_v and not has_risk:
            continue
        rating = "V" if has_v else "N"
        low = "T" if "Low" in marks else "F"
        medium = "T" if "Med" in marks else "F"
        high = "T" if ("High" in marks or "Imminent" in marks) else "F"

        violation_rows.append(
            {
                "_id": "",
                "encounter": encounter,
                "id": client_id,
                "placard_st": placard_st,
                "facility_name": facility_name,
                "bus_st_date": "",
                "description": category_desc,
                "description_new": CATEGORIES[r_num],
                "num": num,
                "street": street,
                "city": city,
                "state": state,
                "zip": zip_code,
                "inspect_dt": inspect_dt,
                "start_time": start_time,
                "end_time": end_time,
                "municipal": municipal,
                "rating": rating,
                "low": low,
                "medium": medium,
                "high": high,
                "url": report_url,
            }
        )

    frozen_marks = {(k, tuple(sorted(v))) for k, v in row_marks.items() if v}
    return inspection_row, violation_rows, frozen_marks


def scrape_directory(input_dir: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], int, int]:
    """
    Walk input_dir, parse all inspection PDFs, deduplicate identical re-uploads,
    and disambiguate any Encounter ID collisions across distinct facilities.
    """
    pdf_paths: List[Path] = []
    for root, _, files in sorted(os.walk(input_dir)):
        for file in sorted(files):
            if file == "inspection_metadata.json":
                continue
            pdf_paths.append(Path(root) / file)

    inspections: List[Dict[str, str]] = []
    violations: List[Dict[str, str]] = []
    seen_Keys: Dict[Tuple[str, str], Set[Tuple[int, Tuple[str, ...]]]] = {}
    used_encounters: Dict[str, str] = {}  # encounter -> client_id
    skipped_non_reports = 0
    skipped_duplicates = 0

    for pdf_path in pdf_paths:
        parsed = parse_pdf(pdf_path, input_dir)
        if parsed is None:
            skipped_non_reports += 1
            continue

        insp_row, viol_rows, frozen_marks = parsed
        enc = insp_row["encounter"]
        cid = insp_row["id"]

        # Deduplicate exact same (encounter, client_id) report uploaded multiple times
        key = (enc, cid)
        if key in seen_Keys and seen_Keys[key] == frozen_marks:
            skipped_duplicates += 1
            continue
        seen_Keys[key] = frozen_marks

        # Disambiguate if two different facilities share the same encounter number on the PDF
        if enc in used_encounters and used_encounters[enc] != cid:
            suffix = 2
            while f"{enc}_{suffix}" in used_encounters:
                suffix += 1
            enc = f"{enc}_{suffix}"
            insp_row["encounter"] = enc
            for v in viol_rows:
                v["encounter"] = enc

        used_encounters[enc] = cid
        inspections.append(insp_row)
        violations.extend(viol_rows)

    # Sort chronologically by inspect_dt, encounter
    inspections.sort(key=lambda r: (r["inspect_dt"], r["encounter"]))
    enc_order = {r["encounter"]: idx for idx, r in enumerate(inspections, start=1)}
    for idx, r in enumerate(inspections, start=1):
        r["_id"] = str(idx)

    violations.sort(key=lambda r: (enc_order.get(r["encounter"], 0), r["description_new"]))
    for idx, v in enumerate(violations, start=1):
        v["_id"] = str(idx)

    return inspections, violations, skipped_non_reports, skipped_duplicates


def write_csv(path: Path, columns: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def combine_with_wprdc(
    wprdc_insp_path: Path,
    wprdc_viol_path: Path,
    accela_insp: List[Dict[str, str]],
    accela_viol: List[Dict[str, str]],
    out_insp_path: Path,
    out_viol_path: Path,
) -> Tuple[int, int, int, int]:
    """Combine WPRDC historical CSVs with newly scraped Accela records, deduplicating by encounter."""
    with open(wprdc_insp_path, newline="", encoding="utf-8") as f:
        w_insp = list(csv.DictReader(f))
    with open(wprdc_viol_path, newline="", encoding="utf-8") as f:
        w_viol = list(csv.DictReader(f))

    w_enc_set = {r["encounter"] for r in w_insp}
    new_a_insp = [dict(r) for r in accela_insp if r["encounter"] not in w_enc_set]
    new_a_enc_set = {r["encounter"] for r in new_a_insp}
    new_a_viol = [dict(r) for r in accela_viol if r["encounter"] in new_a_enc_set]

    max_insp_id = max((int(r["_id"]) for r in w_insp if r.get("_id", "").isdigit()), default=0)
    for idx, r in enumerate(new_a_insp, start=max_insp_id + 1):
        r["_id"] = str(idx)

    max_viol_id = max((int(r["_id"]) for r in w_viol if r.get("_id", "").isdigit()), default=0)
    for idx, r in enumerate(new_a_viol, start=max_viol_id + 1):
        r["_id"] = str(idx)

    comb_insp = w_insp + new_a_insp
    comb_viol = w_viol + new_a_viol

    write_csv(out_insp_path, INSPECTIONS_COLUMNS, comb_insp)
    write_csv(out_viol_path, VIOLATIONS_COLUMNS, comb_viol)
    return len(comb_insp), len(new_a_insp), len(comb_viol), len(new_a_viol)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract ACHD Food Safety Assessment PDFs in data/accela_downloads to CSV."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing downloaded Accela PDFs (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--inspections-out",
        type=Path,
        default=DEFAULT_INSPECTIONS_CSV,
        help=f"Output CSV for inspections (default: {DEFAULT_INSPECTIONS_CSV})",
    )
    parser.add_argument(
        "--violations-out",
        type=Path,
        default=DEFAULT_VIOLATIONS_CSV,
        help=f"Output CSV for violations (default: {DEFAULT_VIOLATIONS_CSV})",
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Also combine with wprdc_inspections.csv and wprdc_violations.csv into data/inspections.csv and data/violations.csv",
    )
    args = parser.parse_args()

    inspections, violations, skipped_non_reports, skipped_duplicates = scrape_directory(args.input_dir)
    write_csv(args.inspections_out, INSPECTIONS_COLUMNS, inspections)
    write_csv(args.violations_out, VIOLATIONS_COLUMNS, violations)

    print(f"Parsed {len(inspections)} unique inspections and {len(violations)} violation rows.")
    print(f"Skipped {skipped_duplicates} duplicate report(s) and {skipped_non_reports} non-inspection file(s).")
    print(f"Wrote inspections to: {args.inspections_out}")
    print(f"Wrote violations to:  {args.violations_out}")

    if args.combine and DEFAULT_WPRDC_INSPECTIONS.exists() and DEFAULT_WPRDC_VIOLATIONS.exists():
        total_i, added_i, total_v, added_v = combine_with_wprdc(
            DEFAULT_WPRDC_INSPECTIONS,
            DEFAULT_WPRDC_VIOLATIONS,
            inspections,
            violations,
            DEFAULT_COMBINED_INSPECTIONS,
            DEFAULT_COMBINED_VIOLATIONS,
        )
        print(f"Combined into {DEFAULT_COMBINED_INSPECTIONS}: {total_i} rows (+{added_i} from Accela)")
        print(f"Combined into {DEFAULT_COMBINED_VIOLATIONS}:  {total_v} rows (+{added_v} from Accela)")


if __name__ == "__main__":
    main()
