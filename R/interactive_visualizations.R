# Widgets are used only in HTML; GitHub Markdown and PDF retain the ggplots.
interactive_output <- function() {
  isTRUE(knitr::opts_knit$get("rmarkdown.pandoc.to") %in% c("html", "html4", "html5"))
}

require_interactive_packages <- function() {
  missing <- c("plotly", "htmlwidgets", "htmltools")[!vapply(
    c("plotly", "htmlwidgets", "htmltools"), requireNamespace, logical(1), quietly = TRUE
  )]
  if (length(missing)) stop("HTML charts require: ", paste(missing, collapse = ", "),
                            ". Install these R packages before rendering HTML.")
}

size_interactive_widget <- function(widget, height) {
  # Quarto otherwise applies a static figure aspect ratio to the widget's
  # outer div while Plotly keeps its pixel height, covering the details panel.
  widget$height <- height
  widget$sizingPolicy <- htmlwidgets::sizingPolicy(
    defaultHeight = height, knitr.figure = FALSE, browser.fill = FALSE, padding = 0
  )
  plotly::config(widget, displaylogo = FALSE, responsive = TRUE)
}

interactive_chart <- function(chart, kind = NULL, height = 520) {
  if (!interactive_output()) return(chart)
  require_interactive_packages()
  escape <- function(x) as.character(htmltools::htmlEscape(as.character(x)))
  data <- chart$data
  if (!is.null(kind)) {
    data$hover <- switch(kind,
      calendar = paste0("<b>", format(data$month, "%B %Y"), "</b><br>",
                        escape(data$visit_type), "<br>Encounters: ", data$n),
      categories = paste0("<b>", escape(data$description_new), "</b><br>",
                          escape(data$severity), "<br>Category records: ", data$NUM_CATEGORIES,
                          " of ", data$total, "<br>Share: ", scales::percent(data$share, accuracy = 0.1)),
      facilities = paste0("<b>", gsub("\n", "<br>", escape(data$label), fixed = TRUE),
                          "</b><br>", escape(data$severity), "<br>Mean categories: ", round(data$mean_count, 2)),
      stop("Unknown interactive chart kind: ", kind)
    )
    chart$data <- data
    chart$mapping$text <- ggplot2::aes(text = hover)$text
  }
  widget <- plotly::ggplotly(chart, tooltip = if (is.null(kind)) "all" else "text", height = height)
  # ggplotly creates extra legend entries for colored text labels. Keep only
  # the actual data traces interactive and give them readable legend names.
  widget$x$data <- lapply(widget$x$data, function(trace) {
    if (identical(trace$mode, "text")) {
      trace$showlegend <- FALSE
      trace$hoverinfo <- "skip"
    }
    if (!is.null(trace$name)) trace$name <- sub("^\\((High|Medium|Low),.*\\)$", "\\1", trace$name)
    trace
  })
  widget <- plotly::layout(widget,
    title = list(text = chart$labels$title, x = 0, xanchor = "left", font = list(size = 19)),
    legend = list(orientation = "h", x = 0, y = 1.02, xanchor = "left", yanchor = "bottom", title = list(text = "")),
    showlegend = !identical(kind, "categories"),
    margin = list(t = 110, b = 70),
    hoverlabel = list(bgcolor = "white", font = list(color = "#172B45")))
  size_interactive_widget(widget, height)
}

followup_widget <- function(pairs, period_label) {
  require_interactive_packages()
  complete <- pairs |>
    dplyr::filter(complete_pair) |>
    dplyr::arrange(name, id) |>
    dplyr::mutate(point_key = paste(initial_score, followup_score, sep = ":"))
  if (!nrow(complete)) return(htmltools::tags$p("No complete follow-up pairs are available for this period."))
  escape <- function(x) as.character(htmltools::htmlEscape(as.character(x)))
  points <- complete |>
    dplyr::summarise(
      facilities = dplyr::n(),
      names_preview = paste(escape(utils::head(name, 6)), collapse = "<br>"),
      .by = c(point_key, initial_score, followup_score)
    ) |>
    dplyr::mutate(
      change = dplyr::case_when(
        followup_score < initial_score ~ "Lower", followup_score > initial_score ~ "Higher",
        .default = "Unchanged"
      ),
      hover = paste0("<b>", facilities, ifelse(facilities == 1, " facility", " facilities"),
                     "</b><br>Initial score: ", initial_score, "<br>Follow-up score: ", followup_score,
                     "<br><br>", names_preview,
                     ifelse(facilities > 6, paste0("<br>...and ", facilities - 6, " more"), ""),
                     "<br><br>Click to see dates and report links for every facility.")
    )
  upper <- max(c(points$initial_score, points$followup_score)) + 3
  widget <- plotly::plot_ly(
    points, x = ~initial_score, y = ~followup_score, type = "scatter", mode = "markers",
    color = ~factor(change, levels = c("Lower", "Unchanged", "Higher")),
    colors = c("#218C8D", "#929DAA", "#B74343"),
    customdata = ~point_key, text = ~hover, hoverinfo = "text",
    marker = list(size = sqrt(points$facilities) * 10, sizemode = "diameter", opacity = 0.85,
                  line = list(color = "white", width = 0.6)), height = 650
  ) |>
    plotly::layout(
      title = list(text = paste0("Next recorded follow-up | ", period_label), x = 0),
      paper_bgcolor = "#FAFBFC", plot_bgcolor = "#FAFBFC", font = list(color = "#172B45"),
      xaxis = list(title = "Initial / Comprehensive score", range = c(-2, upper), zeroline = FALSE,
                   constrain = "domain", tickvals = seq(0, upper, 10)),
      yaxis = list(title = "Next follow-up score", range = c(-2, upper), zeroline = FALSE,
                   scaleanchor = "x", scaleratio = 1, constrain = "domain", tickvals = seq(0, upper, 10)),
      shapes = list(list(type = "line", x0 = 0, y0 = 0, x1 = upper, y1 = upper,
                         line = list(color = "#7D8B9C", dash = "dash"))),
      hoverlabel = list(bgcolor = "white"), hovermode = "closest",
      legend = list(orientation = "h", x = 0, y = 1.08),
      margin = list(l = 65, r = 20, t = 85, b = 65)
    ) |>
    size_interactive_widget(650)

  records <- lapply(seq_len(nrow(complete)), function(i) {
    row <- complete[i, ]
    list(key = row$point_key, name = row$name, id = row$id,
         initial_date = as.character(row$inspect_dt), followup_date = as.character(row$followup_date),
         initial_score = row$initial_score, followup_score = row$followup_score,
         days = row$days_to_followup, purpose = row$followup_purpose,
         initial_report = row$REPORT, followup_report = row$followup_report,
         initial_encounter = row$encounter, followup_encounter = row$followup_encounter)
  })
  htmlwidgets::onRender(widget, paste(readLines("reports/assets/followup-interaction.js", warn = FALSE), collapse = "\n"),
                       data = list(records = records))
}

display_followups <- function(pairs, period_label) {
  if (interactive_output()) followup_widget(pairs, period_label) else plot_followups(pairs, period_label)
}
