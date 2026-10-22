# Run from the repository root: Rscript scripts/build_summaries.R
# Uses the combined dataset (data/inspections.csv and data/violations.csv)
# merging the historical WPRDC exports and scraped Accela PDF reports.
source("R/inspection_analysis.R")

read_export <- function(path) {
  # Preserve facility and encounter identifiers as text.
  read.csv(path, colClasses = "character", check.names = FALSE, na.strings = c("", "NA"))
}

results <- build_inspection_summaries(
  read_export("data/violations.csv"), read_export("data/inspections.csv")
)

dir.create("out", showWarnings = FALSE)
outputs <- c(
  inspections = "violations_by_inspection.csv", yearly = "violations_by_year.csv",
  category_audit = "category_severity_audit.csv", coverage = "coverage.csv",
  excluded_training_facilities = "excluded_training_facilities.csv",
  scope_audit = "inspection_scope_audit.csv"
)
for (key in names(outputs)) {
  write.csv(results[[key]], file.path("out", outputs[[key]]), row.names = FALSE, na = "")
}
print(results$coverage)
