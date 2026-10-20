# Generate the Markdown report without requiring Quarto or a TeX installation.
# Run Rscript clean_inspections.r first. README.md is generated from the QMD.
library(knitr)

lines <- readLines("2025_hall_of_shame.qmd", warn = FALSE)
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
opts_knit$set(rmarkdown.pandoc.to = "gfm")
knit(text = document, output = "README.md", envir = new.env(), quiet = TRUE)
