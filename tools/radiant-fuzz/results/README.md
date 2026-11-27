# Radiant-derived LFCPNX data used by the scripts here (derived data only, no Radiant files)

- **`LFCPNX/tiletypes-cram/GPLL_LLC.ron`, `GPLL_URC.ron`:** the enum-only (CRAM) GPLL tile types from
  the 122-pll-config fuzz. They are the inputs of `../derive_gpll_tiles.py`, which adds pips and
  connections derived from LIFCL:
  - LLC: one row south;
  - URC: LRC mirrored N/S;
  - checked against the Radiant-routed observations in `pll-conns/conns_summary.txt`.

  Rerun `derive_gpll_tiles.py <db> tiletypes-cram <out>` after re-fuzzing. The database's
  `LFCPNX/tiletypes/GPLL_*.ron` were made this way. All four PLL corners lock at 100 MHz from P24 on
  silicon (2026-11-11). Later fuzzers have since corrected some of the derived connections (158, 159).
- **`pll-conns/conns_summary.txt`:** the Radiant-routed PLL pin connections that derive_gpll_tiles.py
  checks against.
- **`pll-params/`:** resolved PLL_CORE parameters from Radiant's PLL generator, one `name=value` file
  per case (see its README).
