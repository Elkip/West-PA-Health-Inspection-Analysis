# Generate annual Markdown reports in out/reports/ from the repository root.
# Run Rscript scripts/build_summaries.R first. Optional arguments select years.
library(knitr)

output_dir <- "out/reports"
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
years <- commandArgs(trailingOnly = TRUE)
inputs <- list.files("reports", pattern = "^20[0-9]{2}\\.qmd$", full.names = TRUE)
available_years <- tools::file_path_sans_ext(basename(inputs))
if (length(years)) {
  if (any(!years %in% available_years)) stop("Unknown report year: ", paste(setdiff(years, available_years), collapse = ", "))
  inputs <- inputs[available_years %in% years]
}
if (!length(inputs)) stop("No annual report sources found. Run this script from the repository root.")

render_qmd_to_md <- function(input_qmd) {
  year <- tools::file_path_sans_ext(basename(input_qmd))
  output_md <- file.path(output_dir, paste0(year, ".md"))
  lines <- readLines(input_qmd, warn = FALSE)
  header_end <- which(lines == "---")[2]
  metadata <- yaml::yaml.load(paste(lines[2:(header_end - 1)], collapse = "\n"))
  body <- lines[(header_end + 1):length(lines)]
  body <- body[body != "\\pagebreak"]
  document <- c(
    paste("#", metadata$title), "", metadata$subtitle, "", "Mitchell Henschel", "", body
  )
  opts_chunk$set(
    echo = FALSE, message = FALSE, error = FALSE,
    fig.width = 8, fig.height = 4.5, dpi = 144
  )
  opts_knit$set(
    rmarkdown.pandoc.to = "gfm", root.dir = normalizePath("."),
    base.dir = normalizePath(output_dir)
  )
  markdown <- knit(text = document, envir = new.env(), quiet = TRUE)
  # Source reports live in reports/; generated Markdown lives in out/reports/.
  markdown <- gsub("](../docs/", "](../../docs/", markdown, fixed = TRUE)
  writeLines(markdown, output_md)
  message("Rendered ", output_md)
}

invisible(lapply(inputs, render_qmd_to_md))
