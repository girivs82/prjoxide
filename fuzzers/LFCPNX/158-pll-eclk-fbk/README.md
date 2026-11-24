# 158-pll-eclk-fbk: the bottom PLLs' dedicated feedback muxes (LFCPNX-100)

The two bottom PLLs can take their feedback from a PLL output through a mux in the bottom-middle
clock tiles, into FBKMUX input JFBKCLK10:
- **ECLKPLLFBR** (R73C75, bits in BMID_1_ECLK_2) feeds PLL_LRC. 002c-clock-tile-pips fuzzed it
  from LIFCL's BMID_1_ECLK_2 arcs.
- **ECLKPLLFBL** (R73C71, bits in BMID_0_ECLK_1) feeds PLL_LLC. LIFCL-40 has no arcs for it, so it
  was missing. 157-dqsbuf-ivref had named its LLCLKOP setting as an enum, BMID.LLC_PLL_FBK.

`fuzzer.py` forces each of ECLKPLLFBL's 12 inputs in a separate design (`fuzz_pip_list`). The inputs
are CLKOP and CLKOS-CLKOS5 of PLL_LLC and PLL_LRC. All 12 build, and their bits are written to
BMID_0_ECLK_1 as pips. The stand-in enum is removed.

**Location:** ECLKPLLFBL's R/C was found by forcing one of its arcs with sv2udb at each R/C of
R70-74 C66-79, as 002c's `--locate` does. Only R73C71 was accepted. The same scan accepted only
R73C75 for ECLKPLLFBR, which matches 002c.

## Bits

Each code is F82 F81 F80 F79, at bit 1 of each frame:

| Input | ECLKPLLFBL (BMID_0_ECLK_1) | ECLKPLLFBR (BMID_1_ECLK_2) |
|---|---|---|
| PLL_LLC CLKOP | 1111 | 1111 |
| PLL_LLC CLKOS | 1101 | 1011 |
| PLL_LLC CLKOS2 | 1110 | 0111 |
| PLL_LLC CLKOS3 | 1100 | 0011 |
| PLL_LLC CLKOS4 | 1011 | 1101 |
| PLL_LLC CLKOS5 | 1001 | 1001 |
| PLL_LRC CLKOP | 1010 | 0101 |
| PLL_LRC CLKOS | 1000 | 0001 |
| PLL_LRC CLKOS2 | 0111 | 1110 |
| PLL_LRC CLKOS3 | 0101 | 1010 |
| PLL_LRC CLKOS4 | 0110 | 0110 |
| PLL_LRC CLKOS5 | 0100 | 0010 |

The two muxes use the same encoding with the bit order reversed (F79-F82 against F82-F79).

## Connections

- GPLL_LLC: added `S1E1:JFBKCLK10_FBMUX_CORE_FBKMUX <- S1E71:JECLKOUT_..._ECLKPLLFBL`. PLL_LLC's
  JFBKCLK10 had no driver in the database.
- GPLL_LRC: changed the driver of `W1:JFBKCLK10_FBMUX_CORE_FBKMUX` from S2W36 to S2W84 (R73C75).
  S2W36 was LIFCL-40's offset (GPLL_LRC R53C87 to its R55C51 mux) copied over.

## Checks with real designs

Each design is a PLL with FBKCK = CLKOP, from the 125 MHz pin. Its CLKOP goes either to an ECLKSYNC,
ECLKDIV and a counter, or to fabric only. The PLL is pinned with `ldc_set_location`. The sources are
SKALP's PLL wrapper and are not published.

| PLL | CLKOP to | Feedback that Radiant chose |
|---|---|---|
| LLC | ECLKSYNC (banks 3, 4, 5) | JFBKCLK10, ECLKPLLFBL = LLCLKOP |
| LLC | fabric | JFBKCLK11 (JCLK1) |
| LRC | ECLKSYNC (bank 3) | JFBKCLK10, ECLKPLLFBR = LRCLKOP |
| LRC | fabric | JFBKCLK11 |
| ULC, URC | fabric | JFBKCLK11 |
| ULC, URC | ECLKSYNC | par refuses: "PLL driving ECLK must be placed at the bottom" |

**The top PLLs:** their FBKMUX has no JFBKCLK10 input in the routing, so they have no dedicated
feedback path.

**Decode:** every design decodes with no unknown bits and packs back to the same FASM. That
includes the PLL IP-bus writes of all four PLLs, with the PLL_CORE iptype.
