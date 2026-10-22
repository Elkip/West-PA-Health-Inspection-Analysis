# Run from the repository root. No additional testing package is required.
source("R/inspection_analysis.R")

inspections <- tibble(
  encounter = c("a1", "a2", "a3", "b1", "c1", "test", "latest", "getgo", "a4", "future"),
  id = c("A", "A", "A", "B", "C", "T", "L", "G", "A", "F"),
  facility_name = c(
    "Shared Name", "Shared Name", "Renamed Facility", "Shared Name", "Only Follow-up",
    "Example (TEST)", "Latest Scoop", "Getgo Corporate Office & Test Kitchen",
    "Renamed Facility", "Outside Coverage"
  ),
  inspect_dt = as.Date(c(
    "2025-01-01", "2025-01-01", "2025-01-03", "2025-01-01", "2025-02-01",
    "2025-03-01", "2025-06-01", "2025-07-31", "2025-07-31", "2025-08-01"
  )),
  num = "10", street = "Main Street", city = "Pittsburgh",
  category_cd = "211", description = "Restaurant without Liquor",
  purpose = c("Initial", "Reinspection", "Initial", "Initial", "Reinspection",
              "Initial", "Initial", "Initial", "Reinspection", "Initial"),
  placard_desc = "Inspected & Permitted"
)
violations <- tibble(
  encounter = c(rep("a1", 5), "a2", "a3", "b1", "c1", "c1", "test", "latest", "getgo"),
  description_new = c(
    "Food Source/Condition", "Probe-Type Thermometers", "Floors", "Administrative", "Toxic Items",
    "Probe-Type Thermometers", "Lighting", "Floors", "Administrative",
    "Probe-Type Thermometers", "Food Source/Condition", "Floors", "Floors"
  ),
  rating = c(rep("V", 4), "N", "N", rep("V", 7)),
  high = c("T", "F", "", NA, "T", "T", "F", "F", "F", "F", "T", "F", "F"),
  medium = c("T", "T", "", NA, "F", "F", "F", "F", "F", "T", "F", "F", "F"),
  low = c("T", "F", "T", NA, "F", "F", "T", "T", "F", "F", "F", "t", "T")
) |>
  left_join(select(inspections, encounter, id, facility_name, inspect_dt), by = "encounter")

results <- build_inspection_summaries(violations, inspections)
visits <- results$inspections
a1 <- filter(visits, encounter == "a1")
stopifnot(
  nrow(visits) == 8,
  !any(visits$encounter %in% c("test", "future")),
  all(c("latest", "getgo") %in% visits$encounter),
  a1$NUM_VIOLATION_CATEGORIES == 4, a1$NUM_HIGH == 1, a1$NUM_MEDIUM == 1,
  a1$NUM_LOW == 1, a1$NUM_UNCLASSIFIED == 1, !a1$SCORE_COMPLETE,
  a1$KNOWN_SEVERITY_SCORE == 9, a1$NUM_NON_VIOLATION_ROWS == 1,
  all(filter(visits, encounter %in% c("a2", "a4"))$NUM_VIOLATION_CATEGORIES == 0),
  filter(visits, encounter == "c1")$NUM_UNCLASSIFIED == 1,
  all(visits$NUM_VIOLATION_CATEGORIES ==
        visits$NUM_HIGH + visits$NUM_MEDIUM + visits$NUM_LOW + visits$NUM_UNCLASSIFIED)
)
a <- filter(results$yearly, id == "A")
stopifnot(
  a$NUM_INSPECTIONS == 4, a$NUM_INITIAL_INSPECTIONS == 2,
  a$NUM_ZERO_RECORDED_VIOLATIONS == 2,
  a$AVG_KNOWN_SEVERITY_SCORE == 2.5, a$AVG_INITIAL_SCORE == 5,
  a$AVG_INITIAL_HIGH == 0.5, a$AVG_INITIAL_MEDIUM == 0.5, a$AVG_INITIAL_LOW == 1,
  a$NUM_INITIAL_UNCLASSIFIED == 1,
  a$LATEST_KNOWN_SEVERITY_SCORE == 0, a$LATEST_NUM_UNCLASSIFIED == 0,
  grepl("a4$", a$REPORT), grepl("Renamed Facility", a$name),
  nrow(filter(results$yearly, id == "B")) == 1,
  is.na(filter(results$yearly, id == "C")$AVG_INITIAL_SCORE)
)

# A high-severity category outranks any number of lower-severity categories.
# Unknown counts must not be treated as extra low-risk points or break ties.
ranks <- rank_inspections(tibble(
  encounter = c("high", "medium", "tied"), inspect_dt = as.Date("2025-01-01"),
  NUM_HIGH = c(1, 0, 1), NUM_MEDIUM = c(0, 10, 0), NUM_LOW = c(0, 10, 0),
  NUM_UNCLASSIFIED = c(0, 0, 5)
))
stopifnot(
  all(filter(ranks, encounter %in% c("high", "tied"))$SEVERITY_RANK == 1),
  filter(ranks, encounter == "medium")$SEVERITY_RANK == 3
)

# All-N exports still produce zero-recorded-violation encounters, not crashes.
no_violations <- build_inspection_summaries(mutate(violations, rating = "N"), inspections)
stopifnot(all(no_violations$inspections$KNOWN_SEVERITY_SCORE == 0))

# A new year is aggregated independently, and an out-of-window visit is excluded.
next_inspection <- mutate(filter(inspections, encounter == "a1"),
                          encounter = "next_year", inspect_dt = as.Date("2026-01-01"))
next_violation <- mutate(filter(violations, encounter == "a1", description_new == "Floors"),
                        encounter = "next_year", inspect_dt = as.Date("2026-01-01"))
two_years <- build_inspection_summaries(
  bind_rows(violations, next_violation), bind_rows(inspections, next_inspection)
)
stopifnot(
  nrow(filter(two_years$yearly, id == "A")) == 2,
  filter(two_years$yearly, id == "A", inspect_yr == 2026)$NUM_INSPECTIONS == 1,
  filter(two_years$yearly, id == "A", inspect_yr == 2025)$NUM_INSPECTIONS == 4
)

expect_error <- function(expression, pattern) {
  error <- tryCatch({ force(expression); NULL }, error = identity)
  stopifnot(inherits(error, "error"), grepl(pattern, conditionMessage(error)))
}
expect_error(build_inspection_summaries(bind_rows(violations, violations[1, ]), inspections), "Duplicate")
expect_error(build_inspection_summaries(violations, bind_rows(inspections, inspections[1, ])), "Duplicate")
expect_error(build_inspection_summaries(mutate(violations, high = "?"), inspections), "severity flag")
expect_error(build_inspection_summaries(mutate(violations, rating = "?"), inspections), "assessment rating")
expect_error(build_inspection_summaries(
  mutate(violations, id = if_else(encounter == "a1", "wrong", id)), inspections
), "metadata")
expect_error(build_inspection_summaries(violations, filter(inspections, encounter != "a2")), "metadata")

# Independent checks against original ACHD PDFs, when the historical exports
# are available locally. These catch erroneous counting of stale N-row flags
# and multiple severity flags within one violation category.
if (file.exists("data/violations.csv") && file.exists("data/inspections.csv")) {
  read_export <- function(path) read.csv(path, colClasses = "character", na.strings = c("", "NA"))
  actual <- build_inspection_summaries(
    read_export("data/violations.csv"), read_export("data/inspections.csv")
  )$inspections
  # https://appsrv.alleghenycounty.us/reports/rwservlet?food_rep_insp&P_ENCOUNTER=202502190003
  cake <- filter(actual, encounter == "202502190003")
  # https://appsrv.alleghenycounty.us/reports/rwservlet?food_rep_insp&P_ENCOUNTER=202503180056
  library_visit <- filter(actual, encounter == "202503180056")
  stopifnot(
    nrow(cake) == 1, cake$NUM_VIOLATION_CATEGORIES == 8,
    cake$NUM_HIGH == 0, cake$NUM_MEDIUM == 2, cake$NUM_LOW == 6,
    cake$NUM_NON_VIOLATION_ROWS == 1, cake$NUM_UNCLASSIFIED == 0,
    nrow(library_visit) == 1, library_visit$NUM_VIOLATION_CATEGORIES == 20,
    library_visit$NUM_HIGH == 5, library_visit$NUM_MEDIUM == 4, library_visit$NUM_LOW == 11,
    library_visit$NUM_UNCLASSIFIED == 0
  )
}
cat("Inspection scoring, aggregation, validation, and report checks passed.\n")
