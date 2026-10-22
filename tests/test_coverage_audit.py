import unittest

from scraper.audit_coverage import compare_months, unique_inventory


class CoverageAuditTests(unittest.TestCase):
    def test_exact_duplicates_only(self):
        record = {"_id": "1", "inspection_id": "a", "facility_type": "Food Facility", "inspect_dt": "2025-08-11"}
        duplicate = dict(record, _id="2")
        self.assertEqual(len(unique_inventory([record, duplicate])), 1)
        with self.assertRaises(ValueError):
            unique_inventory([record, dict(duplicate, inspect_dt="2025-08-12")])

    def test_same_window_and_separate_permanent_counts(self):
        inventory = [
            {"inspect_dt": "2025-08-11", "facility_type": "Food Facility"},
            {"inspect_dt": "2025-08-12", "facility_type": "Mobile Food"},
            {"inspect_dt": "2025-09-15", "facility_type": "Food Facility"},
        ]
        local = [
            {"encounter": "old", "inspect_dt": "2025-08-01"},
            {"encounter": "included", "inspect_dt": "2025-08-11"},
            {"encounter": "excluded", "inspect_dt": "2025-08-12"},
            {"encounter": "later", "inspect_dt": "2025-09-30"},
        ]
        comparison = compare_months(inventory, local, {"old", "included", "later"})
        self.assertEqual(comparison[0]["wprdc_food_facility"], 1)
        self.assertEqual(comparison[0]["local_pdf_all_types"], 2)
        self.assertEqual(comparison[0]["local_pdf_permanent_scope"], 1)
        self.assertEqual(comparison[1]["local_pdf_all_types"], 0)
        self.assertEqual(comparison[1]["wprdc_food_facility"], 1)
        self.assertEqual(comparison[1]["window_end"], "2025-09-15")


if __name__ == "__main__":
    unittest.main()
