#!/usr/bin/env python3
"""Compare the local PDF sample with WPRDC's restored inspection inventory.

Run after scripts/build_summaries.R. The inventory has no violation rows; it is a
coverage benchmark, not an input to risk scores or zero-violation inference.
"""
import argparse
import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = "1c9cf8d8-f3db-4364-b925-d7078c2fb02f"
URL = f"https://data.wprdc.org/datastore/dump/{RESOURCE}"
CACHE = ROOT / "data/wprdc_current_inspections.csv"


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def unique_inventory(rows):
    """Collapse repeated IDs only if all substantive fields agree."""
    unique = {}
    for row in rows:
        key = row["inspection_id"]
        if not key:
            raise ValueError("WPRDC inventory contains a blank inspection ID")
        record = {k: v for k, v in row.items() if k != "_id"}
        if key in unique and unique[key] != record:
            raise ValueError(f"Conflicting records for WPRDC inspection {key}")
        unique[key] = record
    return list(unique.values())


def compare_months(inventory, local, in_scope):
    start = max(min(r["inspect_dt"] for r in inventory), min(r["inspect_dt"] for r in local))
    end = min(max(r["inspect_dt"] for r in inventory), max(r["inspect_dt"] for r in local))
    if start > end:
        raise ValueError("Inventory and local PDF dates do not overlap")
    within = lambda r: start <= r["inspect_dt"] <= end
    official = Counter(r["inspect_dt"][:7] for r in inventory if within(r) and r["facility_type"] == "Food Facility")
    parsed = Counter(r["inspect_dt"][:7] for r in local if within(r))
    scoped = Counter(r["inspect_dt"][:7] for r in local if within(r) and r["encounter"] in in_scope)
    rows = []
    for month in sorted(official.keys() | parsed.keys()):
        rows.append(dict(month=month, wprdc_food_facility=official[month],
                         local_pdf_all_types=parsed[month], local_pdf_permanent_scope=scoped[month],
                         window_start=start, window_end=end))
    return rows


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Download a fresh current WPRDC inventory")
    args = parser.parse_args()
    if args.refresh or not CACHE.exists():
        with urlopen(URL, timeout=60) as response:
            content = response.read().decode("utf-8-sig")
        columns = next(csv.reader(io.StringIO(content)))
        if not {"inspection_id", "facility_type", "inspect_dt"}.issubset(columns):
            raise ValueError("Unexpected WPRDC inventory schema")
        CACHE.write_text(content, encoding="utf-8")
        CACHE.with_suffix(".metadata.json").write_text(json.dumps({
            "resource_id": RESOURCE, "url": URL, "retrieved_at": datetime.now(timezone.utc).isoformat()
        }, indent=2), encoding="utf-8")
    raw = read_csv(CACHE)
    inventory = unique_inventory(raw)
    local = read_csv(ROOT / "data/accela_inspections.csv")
    if len({r["encounter"] for r in local}) != len(local):
        raise ValueError("Duplicate local encounter IDs; reconcile before comparing counts")
    scope = read_csv(ROOT / "out/inspection_scope_audit.csv")
    in_scope = {r["encounter"] for r in scope if r["IN_PERMANENT_SCOPE"] == "TRUE"}
    comparison = compare_months(inventory, local, in_scope)
    types = Counter(r["facility_type"] for r in inventory)
    summary = {
        "resource_id": RESOURCE, "source_url": URL,
        "inventory_rows": len(raw), "unique_inspections": len(inventory),
        "duplicate_rows_removed": len(raw) - len(inventory),
        "inventory_start": min(r["inspect_dt"] for r in inventory),
        "inventory_end": max(r["inspect_dt"] for r in inventory),
        "facility_type_counts": dict(types),
        "comparison_start": comparison[0]["window_start"],
        "comparison_end": comparison[0]["window_end"],
        "wprdc_food_facility_comparison_count": sum(r["wprdc_food_facility"] for r in comparison),
        "local_pdf_all_types_comparison_count": sum(r["local_pdf_all_types"] for r in comparison),
        "local_pdf_permanent_scope_comparison_count": sum(r["local_pdf_permanent_scope"] for r in comparison),
        "interpretation": "Counts over the same dates, not an encounter-matched completeness estimate. Missing PDFs are not zero violations."
    }
    output = ROOT / "out"
    output.mkdir(exist_ok=True)
    write_csv(output / "source_coverage_by_month.csv", comparison, list(comparison[0]))
    write_csv(output / "wprdc_facility_type_counts.csv",
              [dict(facility_type=k, inspections=v) for k, v in sorted(types.items())],
              ["facility_type", "inspections"])
    (output / "source_coverage_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
