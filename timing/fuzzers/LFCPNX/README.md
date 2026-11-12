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
- LRAM, DSP and IOLOGIC pins: the LFCPNX tile types have no routing for these
  blocks yet. EBR arcs use LIFCL's EBR tile connections as candidates, accepted
  only where the trace reaches the SDF source pin.
- 05-clock: PLL, DCC, DCS and ECLKDIV pins are not mapped yet.
