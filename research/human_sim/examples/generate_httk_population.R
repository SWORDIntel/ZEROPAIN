#!/usr/bin/env Rscript

# Generate a correlated adult virtual population for HumanSim using httk.
#
# This script does not generate drug exposures or doses. It only exports demographic,
# anthropometric and physiological rows for the HumanSim population importer.
#
# Usage:
#   Rscript research/human_sim/examples/generate_httk_population.R output.csv 1000 42
#
# Requires:
#   install.packages("httk")

args <- commandArgs(trailingOnly = TRUE)
output <- if (length(args) >= 1) args[[1]] else "httkpop.csv"
nsamp <- if (length(args) >= 2) as.integer(args[[2]]) else 1000L
seed <- if (length(args) >= 3) as.integer(args[[3]]) else 42L

if (is.na(nsamp) || nsamp < 1) {
  stop("nsamp must be a positive integer")
}
if (is.na(seed)) {
  stop("seed must be an integer")
}
if (!requireNamespace("httk", quietly = TRUE)) {
  stop('R package "httk" is required. Install with install.packages("httk").')
}

set.seed(seed)

population <- httk::httkpop_generate(
  method = "direct resampling",
  nsamp = nsamp,
  agelim_years = c(18, 79)
)

write.csv(population, output, row.names = FALSE, quote = TRUE)

cat(sprintf(
  "Wrote %d correlated httk virtual individuals to %s (seed=%d)\n",
  nrow(population), output, seed
))
