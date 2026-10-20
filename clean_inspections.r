# Run from the repository root: Rscript clean_inspections.r
# Use the two matching historical (2014-2025) exports, not the new Accela feed.
# https://data.wprdc.org/dataset/allegheny-county-restaurant-food-facility-inspection-violations
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
  excluded_training_facilities = "excluded_training_facilities.csv"
)
for (key in names(outputs)) {
  write.csv(results[[key]], file.path("out", outputs[[key]]), row.names = FALSE, na = "")
}
print(results$coverage)
