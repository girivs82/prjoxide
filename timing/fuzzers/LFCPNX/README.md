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

12-dqsbuf-ivref: one DQSBUF_IVREF per bank (3, 4, 5) with every input registered, for the
IVREF_CORE IVREFI connections (tools/radiant-fuzz/infer_dqsbuf_conns.py; see
fuzzers/LFCPNX/037-ivref). Not part of the timing solve.

17-osc-pins / 18-eclk-pins: the oscillator and the HP-bank edge-clock blocks, for their fabric
connections (tools/radiant-fuzz/infer_edge_block_conns.py, check_eclk_routing.py). Not part of the
timing solve.

## DDR cell timings (DQSBUF, DDRDLL, ECLKSYNC, ECLKDIV, x4 DQ IO logic)

These come from one Radiant build of a reference x4 LPDDR4 PHY (4 byte lanes, DQSBUF, DDRDLL, two
ECLKSYNCs, ECLKDIV, ODDRX4DQ / TSHX4DQ / IDDRX4DQ with DELAYA, ODDRX4DQS / TSHX4DQS, ODDRX4 +
DELAYB). The design itself is not part of this repository.
- Build: the CLI flow (LSE, postsyn, map, par) at the operating condition of the other tables
  (postsyn's default). An industrial build gives LUT4 / FF delays 1-2 % off the tables; this one
  matches them exactly.
- Backannotation: grades 4-12 and -min.
- Extraction: `extract_cell_timings.py <folder> LFCPNX --out=<dir>`, then
  `merge_cell_timings.py <dir> LFCPNX`. The merge adds only cell types the tables lack and leaves the
  others (LUT4, FF, IOLOGIC:ODDRXN[:DELAYED]) as they are.

Radiant's SDF names the x4 gearing cells MODDRXN / MTDDRXN / MIDDRXN inside a per-pad `*_IOL` cell.
The extractor gives each arc to its sub-cell by its pins:
- an IOL with input gearing is a DQ / DMI pin: IOLOGIC:ODDRX4DQ, TSHX4DQ, IDDRX4DQ (:DELAYED, as the
  input goes through DELAYA);
- one with only output and tristate gearing is a DQS pin: IOLOGIC:ODDRX4DQS, TSHX4DQS;
- a plain ODDRXN (CA / CK) keeps the existing IOLOGIC:ODDRXN[:DELAYED] entries.

The SDF pin `DQSW` of ODDRX4DQ / TSHX4DQ is the primitive's DQSW270 input; `DQSR90` is IDDRX4DQ's.

What Radiant's SDF models, i.e. everything in the tables:

| Cell | Delays | Checks (to clock) |
|---|---|---|
| DQSBUF | ECLKIN -> READCOUT / WRCOUT / WRLVCOUT; RDDIR -> READCOUT; WRDIR -> WRCOUT; WRLVDIR -> WRLVCOUT; SCLK -> DATAVALID | RST to SCLK |
| DDRDLL | CLKIN -> LOCK; RST -> LOCK | none |
| ECLKSYNC | ECLKIN -> ECLKOUT (0) | none |
| ECLKDIV | ECLKIN -> DIVOUT | DIVRST to ECLKIN |
| IOLOGIC:ODDRX4DQ | DQSW -> DOUT; LSROUT -> DOUT | TXDATA, LSROUT, RANK0/1UPDATE to SCLKOUT |
| IOLOGIC:TSHX4DQ | DQSW -> TOUT | TSDATA to SCLKOUT |
| IOLOGIC:IDDRX4DQ:DELAYED | SCLKIN -> RXDATA; LSRIN -> RXDATA | DI, RDPNTR, WRPNTR to DQSR90; LSRIN, ECLK, RANK0/1UPDATE to SCLKIN |
| IOLOGIC:ODDRX4DQS | DQSW -> DOUT; LSROUT -> DOUT | TXDATA, LSROUT to SCLKOUT |
| IOLOGIC:TSHX4DQS | DQSW -> TOUT | TSDATA to SCLKOUT |

The SDF has no arcs for the following, although the design drives every input from a register and
uses every output:
- the DQSBUF's other fabric inputs (READ, RDCLKSEL, PAUSE, READMOVE, RDLOADN, SELCLK, WRMOVE,
  WRLOAD_N, WRLVMOVE, WRLVLOAD_N, RSTSMCNT);
- its other outputs (BTDETECT, BURSTDETECT, DQSWRD, RDPNTR / WRPNTR);
- DDRDLL CODE;
- ECLKSYNC STOP and ECLKDIV SLIP: no checks even where they are driven from registers
  (18-eclk-pins' designs drive every STOP / DIVRST / SLIP; only DIVRST gets one);
- DELAYA / DELAYB's control pins (LOAD_N, MOVE, DIRECTION, COARSE): only their paths to CFLAG, which
  the existing IOLOGIC:DELAY entry has, and CFLAG is unused here.
