source("R/inspection_analysis.R")

records <- tibble(
  id = c("a", "b", "c", "d", "e", "f", "FSP-PERM-1", "FSP-MFF-2", "i", "j", "k", "l"),
  category_cd = c("211", "119", "123", "101", "120", "777", "", "211", "102", "211", "999", ""),
  facility_type = c(rep("", 8), "Food Facility", "Shared Kitchen", "", ""),
  permit_record_id = c(rep("", 11), "FSP-PERM-3")
)
classified <- classify_facility_scope(records)
stopifnot(identical(classified$IN_PERMANENT_SCOPE,
                    c(TRUE, FALSE, FALSE, FALSE, FALSE, TRUE, TRUE, FALSE, TRUE, FALSE, FALSE, TRUE)))

# Scope removal must remove the associated violations, while retaining a real
# zero-violation permanent inspection. This must not depend on a name keyword.
inspections <- tibble(
  encounter = c("p1", "m1", "p2"), id = c("a", "b", "c"),
  facility_name = c("Mobile-themed Cafe", "Food Truck", "School"),
  inspect_dt = as.Date(c("2025-01-01", "2025-01-02", "2025-01-02")),
  num = "1", street = "Main", city = "Pittsburgh", purpose = "Initial",
  placard_desc = "Inspected & Permitted", category_cd = c("211", "123", "651"), description = ""
)
violations <- inspections[1:2, ] |>
  mutate(description_new = "Floors", rating = "V", high = "F", medium = "F", low = "T")
result <- build_inspection_summaries(violations, inspections)
stopifnot(
  nrow(result$inspections) == 2,
  sum(result$inspections$NUM_VIOLATION_CATEGORIES) == 1,
  filter(result$inspections, encounter == "p2")$NUM_VIOLATION_CATEGORIES == 0,
  nrow(result$scope_audit) == 3,
  !filter(result$scope_audit, encounter == "m1")$IN_PERMANENT_SCOPE
)
cat("Permanent establishment scope checks passed.\n")
