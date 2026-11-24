# LFCPNX timing fuzzers

Ports of `timing/fuzzers/LIFCL` to LFCPNX-100 (LFG672), producing
`database/LFCPNX/timing/{cells,interconnect}_<grade>.json` for speed grades
4-12 and M (`backanno -min`). No lapie / udb access is used.

Flow (`timing/tools/fuzzer_lfcpnx.mk`), per generated design:

1. Lattice Synthesis Engine + map + par (`radiant.sh`, readback bitstream).
2. `backanno -sp <grade>` for every grade, and `-min`.
3. The routed pips: `prjoxide unpack` of the readback bitstream.
4. Placement: Radiant's timing report (`timing -sethld`, the Cell/Site column of
   every reported path), par's `.pad` report for IO, and, for cells no report
   names, the routing itself (`timing/util/extract_route_cram.py`).
5. `extract_route_cram.py` traces every SDF interconnect arc from its sink pin
   back to its source pin through the decoded pips and the tile types' fixed
   connections / zero-bit pips, and writes the arc -> pips pickle that
   `timing/util/solve_interconnect.py` uses.

Then, from `timing/`: `tools/postprocess.mk FOLDER=output/LFCPNX` (needs yosys),
`util/solve_interconnect.py output/LFCPNX LFCPNX` (bounded least squares) and
`util/extract_cell_timings.py output/LFCPNX LFCPNX`.

Differences from the LIFCL generators: ECLKSYNC in front of every DDR edge
clock / ECLKDIV (LFCPNX map requires it), LFG672 pins (taken from par `.pad`
reports), and IO standards limited to ones par places together in a bank.

Known coverage limits of the route extraction (those arcs are left out of the
interconnect solve; cell timings come from the SDF and are unaffected):

- Clock nets through the TAPs at columns 14, 38 and 146, whose branch mux bits
  differ from the (LIFCL-derived) LFCPNX TAP tile types.
- IOLOGIC pins, and some LRAM / DSP pins: arcs whose trace does not reach the SDF
  source pin are left out.
- 05-clock: PLL fabric pins and the REFMUX / FBKMUX inputs, and ECLKDIV outputs.
  (DCC, DCS and DLLDEL pins are mapped; the bottom-side DCCs' pin wires are one row
  above their BMID tile, and an unused PCLKDIV passes DCS clock input 0 through.)

12-dqsbuf-ivref: one DQSBUF_IVREF per bank (3, 4, 5) with every input registered, for the
IVREF_CORE IVREFI connections (tools/radiant-fuzz/infer_dqsbuf_conns.py; see
fuzzers/LFCPNX/037-ivref). Not part of the timing solve.

## Untimed switch classes (fabric clock entry, DCS, CIBTEST, span1 -> M, DLLDEL)

Classes that SKALP routed through but the database had no delay for (the K4 report). New
classifications (libprjoxide/prjoxide/src/pip_classes.rs) and designs:

- `JQn_CIBTEST` / `JFn_CIBTEST` take the `q` / `f` wire class: a hard block's output
  (`<block> -> JQn_CIBTEST -> JQn`) is then `<block> -> q` (measured: Radiant's routes show the
  test-mux input as an alias of JQn) plus `q -> q` (zero delay). Same for f.
- `dcsmux_internal`, `dcsmux -> dcs`, and the DCS clock-0 path through the PCLKDIV
  (`dcsmux -> pclkdiv`, `pclkdiv_internal`, `pclkdiv -> dcs`); DLLDEL as a block (`io33 -> dlldel`,
  `dlldel_internal`); global tracks HPRX / VPSX / HPBX 10 and up.
- **20-fabric-clk**: fabric-generated clocks (a register output) driving 48 registers each, the
  source register pinned next to a mid mux's PCLKCIB entry (par refuses a fabric clock whose
  source is elsewhere: "routed with generic routing resources"). Measures `jpclkcib{b,t,l,r}N ->
  j{v,h}pf_mid` / `jpclkcib*_mid_entry` for b0-b5, t0, t2-t5, l0-l3, r0-r3; t1 shares t0's CIB
  and stays untimed.
- **20b-fabric-clk-far**: the far entries r4-r8 / l4-l8, fed from CIBs 13 columns in (C146 /
  C13) in the CIB-only rows 19 / 28 / 46 / 55. With free placement par never uses them; it does
  when the four near entries of the side are taken by other fabric clocks and the centre CMUX
  tiles and the other mid muxes' entry tiles are prohibited (`ldc_prohibit`), with the sources
  pinned in the logic rows next to the far CIBs (gen_fabclk.py ENTRY_LIST / PROHIBIT). Forcing
  just the mid-mux arc with sv2udb (`\dm:arcs`) is accepted but gives no routed path to time.
- **21-m-input**: dense register-to-register copies (data on the slice M input). Radiant enters M
  from span-1 wires only in their own tile; `w1:span1w -> m` / `e1:span1w -> m` are given
  `span1w -> m` (timing_config.py `derived_classes`).
- **22-dlldel**: pad -> DLLDEL -> clock. The pad -> CLKIN connection is dedicated (no routing to
  trace), so `util/add_dlldel_timing.py` takes `io33 -> dlldel` from that SDF arc directly and
  adds the DLLDEL cell (CLKIN -> CLKOUT) to cells_<grade>.json.

Solve: the archived designs were re-extracted with the current database and extractor
(`tools/reextract_lfcpnx.sh <fuzzer dir>...`), then

    FREEZE_FROM=<dir with the previous interconnect_<grade>.json> \
    FREEZE_EXCEPT="_mid|mid -> |_mid_entry|dcc|dcs|cmux|hprx|vpsx|pclkdiv" \
        util/solve_interconnect.py output/LFCPNX LFCPNX
    util/add_dlldel_timing.py output/LFCPNX LFCPNX

FREEZE_FROM keeps every class that already has a value; FREEZE_EXCEPT re-solves the global clock
tree together with the new clock designs (a free solve of everything re-splits collinear classes
and raises the error on the older designs). `util/eval_interconnect.py` gives a json's error on
the routed arcs; `util/class_census.py` counts arcs per class. Grade-9 rms: core designs 44.4 ps
(unchanged), fabric-clock designs 39.5 ps (was 73.6 with the entries untimed), 05-clock 91 ps.
In this solve the near fabric-clock entries come out at 0-7 ps each: the rest of the path (mid -> dcc,
the CMUX and the HPRX / VPSX tree) already accounts for Radiant's delays. The far entries were
then solved with every other class frozen (FREEZE_FROM = the previous result): r4-r8 54-76 ps per
hop (grade 9), l4-l8 0-9 ps; on those arcs the model is within 2 ps of Radiant's.
