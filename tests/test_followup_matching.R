# Check the chronological matching rules used in the portfolio scatterplot.
source("R/inspection_analysis.R")
source("R/visualizations.R")

visits <- tibble(
  id = c(rep("A", 4), rep("B", 3), rep("C", 2), rep("D", 2)),
  encounter = as.character(seq_len(11)),
  inspect_dt = as.Date("2025-01-01") + c(0, 1, 3, 4, 0, 1, 2, 0, 0, 0, 5),
  purpose = c("Initial", "Reinspection", "Initial", "Reinspection",
              "Initial", "Complaint", "Reinspection", "Initial", "Reinspection",
              "Initial", "Partial ReInspection"),
  KNOWN_SEVERITY_SCORE = c(20, 10, 15, 5, 20, 10, 5, 10, 5, 12, 0),
  NUM_UNCLASSIFIED = c(1, rep(0, 10)),
  IS_INITIAL = purpose == "Initial"
)
pairs <- match_followups(visits)
stopifnot(
  nrow(pairs) == 2,
  # Keep the earliest eligible pair, even when a later pair has complete flags.
  filter(pairs, id == "A")$initial_score == 20,
  !filter(pairs, id == "A")$complete_pair,
  # Do not jump over a complaint or infer ordering of same-day visits.
  !any(pairs$id %in% c("B", "C")),
  filter(pairs, id == "D")$followup_score == 0,
  filter(pairs, id == "D")$days_to_followup == 5,
  filter(pairs, id == "D")$complete_pair
)
cat("Follow-up matching checks passed.\n")
