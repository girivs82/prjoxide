# 154-ddrll: the DDRDLLs (LFCPNX-100)

LFCPNX-100 has two DDRDLLs: DDRDLL_CORE_R68C1 on the left (tile CIB_R68C0:DOSCL_P18) and
DDRDLL_CORE_R72C158 on the right (tile CIB_R72C159:DDR_OSC_R).

`fuzzer.py` runs LIFCL's 154-ddrll settings (ENA_OSC, ENA_ROUNDOFF, FORCE_MAX_DELAY, GSR, RSTMUX)
on both. The sites were found by placing a DDRDLL at candidate sites near the DDR tiles.

## Left DDRDLL clock input

The right DDRDLL's CLKIN mux is in DDR_OSC_R (002c-clock-tile-pips): `W1:JCLKOUT_I0` from
`W1:JECLK0_I0` .. `JECLK3_I0` or `W1:JPCLK_I0`. The left one was missing. With it, every design
whose DDRDLL Radiant placed on the left had three unknown bits:
- DOSCL_P18 F9B0 / F11B0;
- DDR40_ECLK_L (CIB_R74C14) F102B1.

They come from a small design: refclk -> ECLKSYNC -> DDRDLL CLKIN, with LOCK captured. The DDRDLL
is pinned to R68C1, and the ECLKSYNC to each edge clock in turn
(`ldc_set_location -site {...} [get_cells u_dll.DDRDLL_inst]` / `[get_cells u_es.ECLKSYNC_inst]`).
The DDRDLL's CODE cannot drive fabric logic (map refuses it), so it is left open.

| CLKIN from | DOSCL_P18 | DDR40_ECLK_L |
|---|---|---|
| ECLKSYNC_CORE_R73C73A (edge clock 0) | F9B0 | F101B1 |
| ECLKSYNC_CORE_R73C73B (edge clock 1) | F9B0, F11B0 | F102B1 |
| ECLKSYNC_CORE_R73C72B (bank 5, edge clock 1) | F9B0, F11B0 | F102B1 |
| ECLKSYNC_CORE_R73C73C (edge clock 2) | F9B0, F10B0 | F103B1 |
| ECLKSYNC_CORE_R73C73D (edge clock 3) | F9B0, F10B0, F11B0 | F104B1 |
| a primary clock (the ECLKDIV output) | F11B0 | - |

These tests separate the clock bits from the code bits:
- The same bank 4 / 5 PHY with DLLCODE tied to 0 on every DQSBUF keeps all three bits.
- With the DDRDLL on the right, none of them is set.

So they belong to the left DDRDLL's clock path, not to its CODE.

`write_left_clkin.py` writes:
- **DOSCL_P18 pips** `JCLKOUT_I0` <- `JECLK0_I0` .. `JECLK3_I0`, `JPCLK_I0`, with the bits above.
  - The wires are tile-local (R68C0), not at LIFCL's N1 offset: sv2udb accepts `R68C0_JCLKOUT_I0`
    from `R68C0_JECLK0_I0` .. `JECLK3_I0` and `R68C0_JPCLK_I0`, and rejects a made-up `JECLK9_I0`.
  - The bits are the same as LIFCL's DOSCL_P18_V18 mux; here they come from Radiant's own routing.
- **DDR40_ECLK_L enums** `ECLKDDRL.ECLK0` .. `ECLK3` (OFF / ON, F101B1 .. F104B1): edge clock k
  feeds the left DDRDLL's mux.
  - It is set for an ECLKSYNC of bank 4 or bank 5 alike.
  - LIFCL has no such bit.
  - Radiant's routing does not name the wires of this step (ECLKCASMUX output to the left
    DDRDLL), so it is an enum, not a pip.

The left DDRDLL's CODE outputs reach the DQSBUFs without a bit of their own. The DQSBUF's
DLLCODE bit (F45B1) is set only for the right DDRDLL; see `../README.md`.
