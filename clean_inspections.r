# This script summarizes the complete list of health code violations which can be downloaded at:
# https://data.wprdc.org/dataset/allegheny-county-restaurant-food-facility-inspection-violations

library(dplyr)
library(glue)
require(stringr)
require(lubridate)
require(tidyr)

violations <- read.csv("data/violations.csv") |>
  filter(!stringr::str_detect(tolower(facility_name), "(test client)|(test)|(test / training client)")) |>
  select(X_id, facility_name, description_new, street, city, inspect_dt, url) |>
  rename(id = X_id, violation = description_new) |>
  mutate(name = glue("{facility_name} - {street}, {city}"), 
    inspect_yr = lubridate::year(inspect_dt),
    risk = case_match(violation,
     c("Probe-Type Thermometers") ~ "LOW",
     c("Cross-Contamination Prevention", "Employee Health") ~ "MED_LOW",
     c("Hot Holding Temperatures", "Pest Management", 
      "Cold Holding Temperatures", "Cleaning and Sanitization",
      "Employee Personal Hygiene", "Food Source/Condition", 
      "Cooling Food", "Reheating Temperatures",
      "Cooking Temperatures") ~ "MED",
     c("Contamination Prevention - Food, Utensils and Equipment",
      "Toilet Room", "Garbage and Refuse", "Administrative",
      "Fabrication, Design, Installation and Maintenance",
      "Ventilation", "Lighting", "Floors", "Walls and ceilings",
      "Dressing rooms and Locker rooms", "General Premises") ~ "HIGH_MED",
     c("Certified Food Protection Manager", "Handwashing Facilities",
        "Toxic Items", "Plumbing", 
        "Consumer Advisory", "Facilities to Maintain Temperature", 
        "Waste Water Disposal", "Water Supply",
         "Demonstration of Knowledge", "Date Marking of Food") ~ "HIGH",
    .default = "UNKNOWN"),
    risk_score = c(LOW = 1, MED_LOW = 2, MED = 3, HIGH_MED = 4, HIGH = 5, UNKNOWN = 0)[risk])

by_inspection <- violations |> 
  summarise(TOTAL_RISK_SCORE = sum(risk_score), 
    TOTAL_VIOLATIONS = n(),
    REPORT = first(url),
    .by = c(name, inspect_dt))

type_by_inspection <- violations |>
  group_by(name, inspect_dt) |>
  count(risk) |>
  pivot_wider(names_from = risk, values_from = n, values_fill = 0, names_prefix = "NUM_")

violations_by_inspection <- by_inspection |>
  inner_join(type_by_inspection, join_by("name", "inspect_dt")) |>
  relocate("name", "inspect_dt", "REPORT", "TOTAL_RISK_SCORE", "TOTAL_VIOLATIONS", "NUM_LOW", "NUM_MED_LOW", "NUM_MED", "NUM_HIGH_MED", "NUM_HIGH")

write.csv(violations_by_inspection, "out/violations_by_inspection.csv")

by_year <- violations |>
  summarise(TOTAL_RISK_SCORE = sum(risk_score), 
    NUM_INSPECTIONS = n_distinct(inspect_dt), 
    TOTAL_VIOLATIONS = n(),
    REPORT = first(url),
    .by = c(name, inspect_yr)) |>
  mutate(AVG_RISK_SCORE = TOTAL_RISK_SCORE / NUM_INSPECTIONS)

type_by_year <- violations |>
  group_by(name, inspect_yr) |>
  count(risk) |>
  tidyr::pivot_wider(names_from = risk, values_from = n, values_fill = 0, names_prefix = "NUM_")

violations_by_year <- by_year |>
  inner_join(type_by_year, join_by("name", "inspect_yr")) |>
  relocate("name", "inspect_yr", "REPORT", "TOTAL_RISK_SCORE", "NUM_INSPECTIONS", "AVG_RISK_SCORE", "NUM_LOW", "NUM_MED_LOW", "NUM_MED", "NUM_HIGH_MED", "NUM_HIGH")

write.csv(violations_by_year, "out/violations_by_year.csv")

rm(list = ls())
