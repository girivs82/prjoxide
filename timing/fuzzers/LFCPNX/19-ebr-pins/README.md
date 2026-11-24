# 19-ebr-pins: EBR pin connections checked against Radiant's routing (LFCPNX-100)

The EBR tile types (EBR_1 / EBR_4 / EBR_7 / EBR_9) have LIFCL's connections between CIB wires and
the EBR_CORE pins. This fuzzer checks them against Radiant's own routing. It was prompted by a
board symptom: SKALP's x36 PDPSC16K lost write-data bits DIA17, DIB0 and DIB1.

**Designs.** `gen_ebr_pins.py` makes 48 EBRs per design:
- the primitive is chosen at random among DP16K x18/x18, PDP16K x36 and PDPSC16K x36;
- every input pin is driven by its own fabric register, and every output is captured by its own
  register.

The flow is `tools/fuzzer_lfcpnx.mk` with backanno at grade 9 only. Six designs used about 105 EBR
sites:

| Tile type | EBR_1 | EBR_4 | EBR_7 | EBR_9 |
|---|---|---|---|---|
| Sites | 28 | 26 | 24 | 27 |

**Inference.** The script is `tools/radiant-fuzz/infer_ebr_conns.py <out.json> 19-ebr-pins --vote --check`,
run in the container with PYTHONPATH set to util/common, util/fuzz, timing/util and tools/radiant-fuzz.
- **Inputs:** for each pin, the candidate CIBMUX / CE / LSR / CLK wires near the block that the
  source register's net reaches, intersected over all its arcs. This works as in
  infer_block_conns.py for LRAM.
- **Outputs:** the route from an EBR output starts at a CIB wire that only the tile type's fixed
  connections drive. Tracing it backward from the capture register therefore ends at the EBR pin.
  `--check` counts the arcs whose trace ends at exactly the pin the SDF names.

**Result: the database's connections are right.**
- **Inputs:** all 76 CIB-routed input pins of each tile type (304 in all) resolve unanimously over
  67-76 arcs each, and every one equals the database's connection:
  - ADA0-13 and ADB0-13;
  - CSA0-2 and CSB0-2;
  - CEA, CEB, WEA, WEB, RSTA, RSTB;
  - DIA0-17 and DIB0-17.
- **Outputs:** all 36 output pins of each tile type (DOA0-17 and DOB0-17, 144 in all) are confirmed
  by 10368 arcs, with no contradicting arc.
- **Clocks:** CLKA / CLKB come from the global clock network, not from CIB wires.
- **No changes:** nothing in the database was changed.

**x36 logical-to-physical mapping.** In Radiant's backannotated netlist, PDPSC16K / PDP16K at x36 map
as follows. This is the same as nextpnr's and SKALP's mapping.

| Logical bits | EBR_CORE pins |
|---|---|
| DI0-17 | DIA0-17 |
| DI18-35 | DIB0-17 |
| DO0-17 | DOB0-17 |
| DO18-35 | DOA0-17 |
