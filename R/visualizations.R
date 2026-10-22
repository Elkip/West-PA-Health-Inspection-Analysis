# Shared visual language and portfolio figures. Inputs are the audited summaries.
library(ggplot2)

severity_colors <- c(High = "#B74343", Medium = "#DEA83B", Low = "#218C8D", Unclassified = "#929DAA")

theme_portfolio <- function() {
  theme_minimal(base_size = 12, base_family = "sans") +
    theme(
      plot.background = element_rect(fill = "#FAFBFC", color = NA),
      panel.background = element_rect(fill = "#FAFBFC", color = NA),
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(color = "#E5EAF0", linewidth = 0.3),
      plot.title = element_text(size = 19, face = "bold", color = "#172B45"),
      plot.subtitle = element_text(size = 11, color = "#52647A", margin = margin(b = 16)),
      plot.caption = element_text(size = 9, color = "#52647A", hjust = 0, margin = margin(t = 14)),
      plot.title.position = "plot", plot.caption.position = "plot",
      axis.title = element_text(color = "#52647A"),
      axis.text = element_text(color = "#172B45"),
      legend.position = "top", legend.justification = "left", legend.title = element_blank(),
      plot.margin = margin(18, 24, 18, 18)
    )
}

plot_inspection_activity <- function(inspections, period_label = "2025-2026") {
  activity <- inspections |>
    mutate(
      month = as.Date(format(inspect_dt, "%Y-%m-01")),
      visit_type = factor(case_when(
        purpose %in% c("Initial", "Comprehensive") ~ "Initial / Comprehensive",
        purpose %in% c("Reinspection", "Partial ReInspection") ~ "Follow-up",
        .default = "Other / mixed"
      ), levels = c("Initial / Comprehensive", "Follow-up", "Other / mixed"))
    ) |>
    count(month, visit_type)
  totals <- summarise(activity, n = sum(n), .by = month)
  n_months <- length(unique(activity$month))
  date_lbl <- if (n_months > 12) "%b\n'%y" else "%b"
  ggplot(activity, aes(month, n, fill = visit_type)) +
    geom_col(width = 21, position = position_stack(reverse = TRUE)) +
    geom_text(data = totals, inherit.aes = FALSE,
              mapping = aes(x = month, y = n, label = scales::comma(n)),
              vjust = -0.7, color = "#172B45", fontface = "bold", size = 3.4) +
    scale_fill_manual(values = c("Initial / Comprehensive" = "#172B45", "Follow-up" = "#218C8D", "Other / mixed" = "#B9C8D8")) +
    scale_x_date(date_labels = date_lbl, date_breaks = "1 month") +
    scale_y_continuous(labels = scales::comma, expand = expansion(mult = c(0, 0.12))) +
    labs(title = "The available inspection records",
         subtitle = paste0("Recorded encounters by month and purpose | Allegheny County, ", period_label),
         x = NULL, y = "Inspection encounters",
         caption = "Source: ACHD / WPRDC historical exports and Accela PDFs, restricted to permanent-establishment scope.\nPost-transition counts are an incomplete PDF sample, not all county inspections; see the source coverage audit.") +
    theme_portfolio() + theme(panel.grid.major.x = element_blank())
}

plot_category_severity <- function(audit, period_label = "2025-2026") {
  top_categories <- audit |>
    summarise(total = sum(NUM_CATEGORIES), .by = description_new) |>
    arrange(desc(total), description_new) |>
    slice_head(n = 15)
  cells <- audit |>
    summarise(NUM_CATEGORIES = sum(NUM_CATEGORIES), .by = c(description_new, severity)) |>
    semi_join(top_categories, by = "description_new") |>
    mutate(severity = factor(severity, levels = c("HIGH", "MEDIUM", "LOW", "UNCLASSIFIED"))) |>
    tidyr::complete(description_new, severity, fill = list(NUM_CATEGORIES = 0)) |>
    left_join(top_categories, by = "description_new") |>
    mutate(share = NUM_CATEGORIES / total,
           category = factor(description_new, levels = rev(top_categories$description_new)))
  labels <- setNames(paste0(stringr::str_wrap(top_categories$description_new, 40),
                            "  (n=", scales::comma(top_categories$total), ")"), top_categories$description_new)
  ggplot(cells, aes(severity, category, fill = share)) +
    geom_tile(color = "#FAFBFC", linewidth = 2, width = 0.97, height = 0.97) +
    geom_text(aes(label = scales::percent(share, accuracy = 1), color = share >= 0.5),
              size = 3.7, fontface = "bold", show.legend = FALSE) +
    scale_color_manual(values = c("FALSE" = "#172B45", "TRUE" = "white")) +
    scale_fill_gradient(low = "#EDF2F6", high = "#12696C", limits = c(0, 1),
                        labels = scales::label_percent(), name = "Share within category",
                        guide = guide_colorbar(barwidth = grid::unit(6, "cm"), title.position = "top")) +
    scale_x_discrete(position = "top", labels = c("High", "Medium", "Low", "Unclassified"), expand = c(0, 0)) +
    scale_y_discrete(labels = labels, expand = c(0, 0)) +
    labs(title = "Same category. Different severity.",
         subtitle = paste0("15 most frequently cited categories | Share at each highest recorded severity, ", period_label),
         x = NULL, y = NULL,
         caption = "Source: ACHD / WPRDC & Accela reports. Only rating = V; all inspection purposes. Each row sums to 100% before rounding.\nn counts inspection/category records, not individual findings. Unclassified means no true severity flag.") +
    theme_portfolio() + theme(panel.grid = element_blank(), legend.position = "bottom",
                             legend.title = element_text(size = 10, color = "#52647A"),
                             axis.text.y = element_text(size = 10))
}

plot_facility_profiles <- function(initial_yearly, period_label = "2025-2026") {
  facilities <- initial_yearly |>
    slice_head(n = 15) |>
    mutate(label = paste0(stringr::str_wrap(sub(", [^,]+$", "", name), 43),
                          "\nN=", NUM_INITIAL_INSPECTIONS, " | U=", NUM_INITIAL_UNCLASSIFIED),
           label = factor(label, levels = rev(label)))
  profiles <- facilities |>
    select(label, High = AVG_INITIAL_HIGH, Medium = AVG_INITIAL_MEDIUM, Low = AVG_INITIAL_LOW) |>
    tidyr::pivot_longer(-label, names_to = "severity", values_to = "mean_count") |>
    mutate(severity = factor(severity, levels = c("High", "Medium", "Low")))
  ggplot(profiles, aes(mean_count, label, fill = severity)) +
    geom_col(width = 0.65, position = position_stack(reverse = TRUE)) +
    geom_text(aes(label = ifelse(mean_count >= 1, format(round(mean_count, 1), trim = TRUE), ""), color = severity),
              position = position_stack(vjust = 0.5, reverse = TRUE), size = 3.5, show.legend = FALSE) +
    scale_color_manual(values = c(High = "white", Medium = "#172B45", Low = "white")) +
    scale_fill_manual(values = severity_colors, drop = FALSE) +
    scale_x_continuous(expand = expansion(mult = c(0, 0.05))) +
    labs(title = "What drives the severity-first ranking?",
         subtitle = paste0("Top 15 facilities | Mean category counts on Initial/Comprehensive inspections, ", period_label),
         x = "Mean recorded categories per Initial/Comprehensive inspection", y = NULL,
         caption = "Source: ACHD / WPRDC & Accela reports. Ordered by mean High, then Medium, then Low; bar length is not rank.\nN = Initial/Comprehensive visits; U = total unclassified categories (excluded from bars). One visit does not establish a pattern.") +
    theme_portfolio() + theme(panel.grid.major.y = element_blank(), axis.text.y = element_text(size = 10))
}

match_followups <- function(inspections) {
  # Match chronological neighbors, not arbitrary later visits. Never bridge
  # another Initial, complaint, or service visit. Keep one pair per facility.
  inspections |>
    arrange(id, inspect_dt, encounter) |>
    group_by(id) |>
    mutate(followup_date = lead(inspect_dt), followup_purpose = lead(purpose),
           followup_report = lead(REPORT), followup_encounter = lead(encounter),
           followup_score = lead(KNOWN_SEVERITY_SCORE),
           followup_unclassified = lead(NUM_UNCLASSIFIED)) |>
    filter(IS_INITIAL, followup_date > inspect_dt,
           followup_purpose %in% c("Reinspection", "Partial ReInspection")) |>
    slice_head(n = 1) |>
    ungroup() |>
    mutate(initial_score = KNOWN_SEVERITY_SCORE,
           days_to_followup = as.integer(followup_date - inspect_dt),
           complete_pair = NUM_UNCLASSIFIED == 0 & followup_unclassified == 0)
}

plot_followups <- function(pairs, period_label = "2025-2026") {
  complete <- filter(pairs, complete_pair)
  if (!nrow(complete)) stop("No complete Initial/follow-up pairs available for the plot.")
  points <- complete |>
    count(initial_score, followup_score, name = "facilities") |>
    mutate(change = factor(case_when(
      followup_score < initial_score ~ "Lower", followup_score > initial_score ~ "Higher",
      .default = "Unchanged"
    ), levels = c("Lower", "Unchanged", "Higher")))
  upper <- max(c(points$initial_score, points$followup_score)) + 3
  ggplot(points, aes(initial_score, followup_score)) +
    annotate("polygon", x = c(0, upper, upper), y = c(0, 0, upper), fill = "#218C8D", alpha = 0.05) +
    geom_abline(slope = 1, intercept = 0, linetype = "dashed", color = "#7D8B9C", linewidth = 0.5) +
    geom_point(aes(size = facilities, fill = change), shape = 21, color = "white", stroke = 0.45, alpha = 0.85) +
    scale_fill_manual(values = c(Lower = "#218C8D", Unchanged = "#929DAA", Higher = "#B74343"), drop = FALSE) +
    scale_size_area(max_size = 9, name = "Facilities", breaks = c(1, 5, 10, 20)) +
    scale_x_continuous(breaks = seq(0, ceiling(upper / 10) * 10, 10)) +
    scale_y_continuous(breaks = seq(0, ceiling(upper / 10) * 10, 10)) +
    coord_equal(xlim = c(-2, upper), ylim = c(-2, upper), expand = FALSE) +
    guides(fill = guide_legend(order = 1, override.aes = list(size = 4)),
           size = guide_legend(order = 2, override.aes = list(fill = "#63758B", color = "#63758B"))) +
    labs(title = "The next visit often tells a different story",
         subtitle = paste0(nrow(complete), " matched facilities | Median gap: ",
                           median(complete$days_to_followup), " days | ", period_label),
         x = "Initial/Comprehensive inspection: known-severity score", y = "Next follow-up: known-severity score", fill = "Score change",
         caption = paste0("Source: ACHD / WPRDC & Accela reports. Below the diagonal = lower score; bubble area = number of facilities.\n",
                          sum(!pairs$complete_pair), " pairs omitted for unclassified categories. Follow-up scope may be narrower; this is not a causal effect.")) +
    theme_portfolio() + theme(legend.title = element_text(size = 10, color = "#52647A"), legend.box = "vertical")
}
