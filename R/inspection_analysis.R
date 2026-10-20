# ACHD severity is recorded on each inspection/category row, not fixed by
# category name. See README.md for source links and interpretation.
library(dplyr)

require_columns <- function(data, columns, label) {
  missing <- setdiff(columns, names(data))
  if (length(missing)) {
    stop(label, " is missing columns: ", paste(missing, collapse = ", "))
  }
}

is_training_name <- function(name) {
  # Explicit test-client markers/names; retain Latest Scoop and the real
  # Getgo Corporate Office & Test Kitchen (both lost by the old substring filter).
  !is.na(name) & grepl(
    "\\(test(?: / training)?(?: client)?\\)|^test\\b|\\btest$",
    trimws(name), ignore.case = TRUE, perl = TRUE
  )
}

rank_inspections <- function(data) {
  data |>
    mutate(SEVERITY_RANK = min_rank(data.frame(
      high = -NUM_HIGH, medium = -NUM_MEDIUM, low = -NUM_LOW
    ))) |>
    arrange(SEVERITY_RANK, desc(inspect_dt), encounter)
}

build_inspection_summaries <- function(violations, inspections) {
  require_columns(violations, c(
    "encounter", "id", "facility_name", "inspect_dt", "description_new",
    "rating", "low", "medium", "high"
  ), "Violations")
  require_columns(inspections, c(
    "encounter", "id", "facility_name", "inspect_dt", "num", "street", "city",
    "purpose", "placard_desc"
  ), "Inspections")
  if (!nrow(violations) || !nrow(inspections)) stop("Both source tables must contain records.")

  normalize <- function(data) {
    data <- data |>
      mutate(across(c(encounter, id), as.character), inspect_dt = as.Date(inspect_dt))
    if (anyNA(data[c("encounter", "id", "inspect_dt")]) ||
        any(data$encounter == "" | data$id == "")) {
      stop("Missing inspection/facility identifiers or invalid dates.")
    }
    data
  }
  violations <- normalize(violations)
  inspections <- normalize(inspections)

  excluded <- bind_rows(
    select(violations, id, facility_name), select(inspections, id, facility_name)
  ) |>
    filter(is_training_name(facility_name)) |>
    distinct(id, facility_name)
  violations <- anti_join(violations, distinct(excluded, id), by = "id")
  inspections <- anti_join(inspections, distinct(excluded, id), by = "id")
  if (!nrow(violations) || !nrow(inspections)) stop("No records remain after training-client exclusions.")

  # Do not treat inspections outside the violation export's observed window
  # as zero-violation visits when combining differently dated downloads.
  coverage_start <- max(min(violations$inspect_dt), min(inspections$inspect_dt))
  coverage_end <- min(max(violations$inspect_dt), max(inspections$inspect_dt))
  if (coverage_start > coverage_end) stop("Source date ranges do not overlap.")
  in_window <- function(data) {
    filter(data, inspect_dt >= coverage_start, inspect_dt <= coverage_end)
  }
  violations <- in_window(violations)
  inspections <- in_window(inspections)

  if (anyDuplicated(inspections$encounter)) stop("Duplicate inspection encounter IDs.")
  if (anyDuplicated(violations[c("encounter", "description_new")])) {
    stop("Duplicate inspection/category rows; resolve these before scoring.")
  }
  if (anyNA(violations$description_new) || any(violations$description_new == "")) {
    stop("Missing assessment category.")
  }
  if (nrow(anti_join(violations, inspections, by = c("encounter", "id", "inspect_dt")))) {
    stop("Violation records have unmatched or inconsistent inspection metadata.")
  }

  violations <- violations |>
    mutate(across(c(rating, low, medium, high), ~ toupper(trimws(as.character(.x)))))
  if (anyNA(violations$rating) || any(!violations$rating %in% c("V", "N"))) {
    stop("Unexpected assessment rating; confirm its meaning before scoring.")
  }
  flags <- unlist(violations[c("low", "medium", "high")], use.names = FALSE)
  if (any(!is.na(flags) & !flags %in% c("T", "F", ""))) {
    stop("Unexpected severity flag; expected T, F, or blank.")
  }

  scored <- violations |>
    filter(rating == "V") |>
    mutate(
      # A category can contain several findings/flags. Count it once at the
      # highest flagged severity; these are category counts, not finding counts.
      severity = case_when(
        high == "T" ~ "HIGH",
        medium == "T" ~ "MEDIUM",
        low == "T" ~ "LOW",
        .default = "UNCLASSIFIED"
      )
    )

  counts <- scored |>
    summarise(
      NUM_VIOLATION_CATEGORIES = n(),
      NUM_HIGH = sum(severity == "HIGH"),
      NUM_MEDIUM = sum(severity == "MEDIUM"),
      NUM_LOW = sum(severity == "LOW"),
      NUM_UNCLASSIFIED = sum(severity == "UNCLASSIFIED"),
      .by = encounter
    )
  source_counts <- violations |>
    summarise(
      NUM_SOURCE_ROWS = n(), NUM_NON_VIOLATION_ROWS = sum(rating != "V"),
      .by = encounter
    )
  count_columns <- c(
    "NUM_VIOLATION_CATEGORIES", "NUM_HIGH", "NUM_MEDIUM", "NUM_LOW",
    "NUM_UNCLASSIFIED", "NUM_SOURCE_ROWS", "NUM_NON_VIOLATION_ROWS"
  )

  by_inspection <- inspections |>
    select(encounter, id, facility_name, num, street, city, inspect_dt, purpose, placard_desc) |>
    left_join(counts, by = "encounter") |>
    left_join(source_counts, by = "encounter") |>
    mutate(
      across(all_of(count_columns), ~ coalesce(.x, 0L)),
      name = paste0(
        facility_name, " - ", trimws(paste(coalesce(num, ""), coalesce(street, ""))),
        ", ", coalesce(city, "")
      ),
      inspect_yr = as.integer(format(inspect_dt, "%Y")),
      REPORT = paste0(
        "https://appsrv.alleghenycounty.us/reports/rwservlet?food_rep_insp&P_ENCOUNTER=", encounter
      ),
      KNOWN_SEVERITY_SCORE = 5 * NUM_HIGH + 3 * NUM_MEDIUM + NUM_LOW,
      SCORE_COMPLETE = NUM_UNCLASSIFIED == 0,
      IS_INITIAL = !is.na(purpose) & purpose == "Initial"
    ) |>
    arrange(inspect_dt, encounter)

  mean_initial <- function(x, initial) if (any(initial)) mean(x[initial]) else NA_real_
  by_year <- by_inspection |>
    summarise(
      name = last(name),
      NUM_INSPECTIONS = n(),
      NUM_INITIAL_INSPECTIONS = sum(IS_INITIAL),
      NUM_ZERO_RECORDED_VIOLATIONS = sum(NUM_VIOLATION_CATEGORIES == 0),
      TOTAL_KNOWN_SEVERITY_SCORE = sum(KNOWN_SEVERITY_SCORE),
      AVG_KNOWN_SEVERITY_SCORE = mean(KNOWN_SEVERITY_SCORE),
      AVG_INITIAL_SCORE = mean_initial(KNOWN_SEVERITY_SCORE, IS_INITIAL),
      AVG_INITIAL_HIGH = mean_initial(NUM_HIGH, IS_INITIAL),
      AVG_INITIAL_MEDIUM = mean_initial(NUM_MEDIUM, IS_INITIAL),
      AVG_INITIAL_LOW = mean_initial(NUM_LOW, IS_INITIAL),
      NUM_INITIAL_UNCLASSIFIED = sum(NUM_UNCLASSIFIED[IS_INITIAL]),
      LATEST_INSPECTION_DATE = last(inspect_dt),
      LATEST_PURPOSE = last(purpose),
      LATEST_KNOWN_SEVERITY_SCORE = last(KNOWN_SEVERITY_SCORE),
      LATEST_NUM_UNCLASSIFIED = last(NUM_UNCLASSIFIED),
      REPORT = last(REPORT),
      NUM_VIOLATION_CATEGORIES = sum(NUM_VIOLATION_CATEGORIES),
      NUM_HIGH = sum(NUM_HIGH), NUM_MEDIUM = sum(NUM_MEDIUM), NUM_LOW = sum(NUM_LOW),
      NUM_UNCLASSIFIED = sum(NUM_UNCLASSIFIED),
      .by = c(id, inspect_yr)
    )

  category_audit <- scored |>
    count(description_new, severity, name = "NUM_CATEGORIES")
  coverage <- data.frame(
    COVERAGE_START = coverage_start, COVERAGE_END = coverage_end,
    NUM_INSPECTIONS = nrow(by_inspection),
    NUM_SOURCE_ROWS = nrow(violations),
    NUM_NON_VIOLATION_ROWS = sum(violations$rating != "V"),
    NUM_VIOLATION_CATEGORIES = nrow(scored),
    NUM_UNCLASSIFIED = sum(scored$severity == "UNCLASSIFIED")
  )
  list(
    inspections = by_inspection, yearly = by_year, category_audit = category_audit,
    coverage = coverage, excluded_training_facilities = excluded
  )
}
