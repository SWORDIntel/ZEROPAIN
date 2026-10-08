#!/usr/bin/env Rscript

# Export reduced HumanSim partition coefficients from httk's Schmitt backend.
#
# This generates partition predictions only. It deliberately does NOT convert
# httk intrinsic-clearance assay outputs into whole-organ HumanSim clearance.
#
# Usage:
#   Rscript generate_httk_disposition.R name "bisphenol a" output.csv
#   Rscript generate_httk_disposition.R cas 80-05-7 output.csv
#   Rscript generate_httk_disposition.R dtxsid DTXSID7020182 output.csv
#
# Output values are tissue-to-UNBOUND-plasma coefficients (Ktissue2pu).
# HumanSim converts them to total tissue:total plasma Kp using fu_plasma separately.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) {
  stop("usage: generate_httk_disposition.R <name|cas|dtxsid> <identifier> <output.csv>")
}

kind <- tolower(args[[1]])
identifier <- args[[2]]
output <- args[[3]]

if (!requireNamespace("httk", quietly = TRUE)) {
  stop('R package "httk" is required. Install with install.packages("httk").')
}

if (!kind %in% c("name", "cas", "dtxsid")) {
  stop("identifier kind must be name, cas, or dtxsid")
}

query <- list(
  species = "Human",
  suppress.messages = TRUE,
  tissuelist = list(
    brain = c("brain"),
    liver = c("liver"),
    kidney = c("kidney")
  )
)
if (kind == "name") query$chem.name <- identifier
if (kind == "cas") query$chem.cas <- identifier
if (kind == "dtxsid") query$dtxsid <- identifier

params <- do.call(httk::parameterize_pbtk, query)

required <- c(
  brain = "Kbrain2pu",
  liver = "Kliver2pu",
  kidney = "Kkidney2pu",
  peripheral = "Krest2pu"
)
missing <- required[!required %in% names(params)]
if (length(missing) > 0) {
  stop(sprintf(
    "httk result missing expected reduced partition parameters: %s",
    paste(missing, collapse = ", ")
  ))
}

rows <- data.frame(
  tissue = names(required),
  value = as.numeric(unlist(params[required])),
  basis = rep("tissue_to_unbound_plasma", length(required)),
  source_id = rep("httk_schmitt", length(required)),
  method = rep("httk parameterize_pbtk: Schmitt 2008 + Pearce calibration", length(required)),
  stringsAsFactors = FALSE
)

if (any(!is.finite(rows$value)) || any(rows$value <= 0)) {
  stop("httk returned non-finite or non-positive partition coefficients")
}

write.csv(rows, output, row.names = FALSE, quote = TRUE)

cat(sprintf(
  "Wrote %d reduced tissue partition coefficients to %s\n",
  nrow(rows), output
))
if ("Funbound.plasma" %in% names(params)) {
  cat(sprintf("Funbound.plasma=%g\n", as.numeric(params[["Funbound.plasma"]])))
}
if ("Rblood2plasma" %in% names(params)) {
  cat(sprintf("Rblood2plasma=%g\n", as.numeric(params[["Rblood2plasma"]])))
}
