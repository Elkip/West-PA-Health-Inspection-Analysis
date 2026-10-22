# Scope is permit type, not inspection purpose or current operating status.
# Historical WPRDC exports have no permit-type field. See docs/data-coverage.md.
classify_facility_scope <- function(inspections) {
  optional <- function(column) {
    if (column %in% names(inspections)) coalesce(as.character(inspections[[column]]), "")
    else rep("", nrow(inspections))
  }
  permit <- optional("permit_record_id")
  permit <- ifelse(permit == "", as.character(inspections$id), permit)
  type <- optional("facility_type")
  code <- trimws(as.character(inspections$category_cd))
  # Fixed-site historical categories, including schools, hospitals, and pools.
  # "Seasonal/Pool Snack Bar" (777) is not a temporary market stand permit.
  permanent_codes <- c(
    "100", "111", "112", "113", "114", "115", "116", "117", "118", "151", "152", "172",
    "201", "202", "203", "211", "212", "250", "303", "304", "305", "306", "307", "308",
    "309", "313", "314", "315", "316", "317", "401", "402", "403", "405", "407", "408",
    "409", "410", "411", "412", "413", "414", "651", "653", "655", "656", "707", "708", "777"
  )
  inspections |>
    mutate(
      SCOPE_BASIS = case_when(
        grepl("^FSP-PERM-", permit) ~ "Permanent permit record",
        grepl("^FSP-", permit) ~ "Other Accela permit record",
        type == "Food Facility" ~ "WPRDC Food Facility type",
        type %in% c("Mobile Food", "Temporary Food", "Fish Fry", "Shared Kitchen", "Commissary") ~ "Other WPRDC facility type",
        type != "" ~ "Unrecognized facility type",
        code %in% c("119", "123", "333", "334", "444", "555") ~ "Mobile or temporary category",
        code %in% c("101", "102", "120", "121") ~ "Shared-kitchen/commissary category: permit type ambiguous",
        code %in% permanent_codes ~ "Historical permanent-category proxy",
        .default = "Missing or unrecognized category"
      ),
      IN_PERMANENT_SCOPE = SCOPE_BASIS %in% c(
        "Permanent permit record", "WPRDC Food Facility type", "Historical permanent-category proxy"
      )
    )
}
