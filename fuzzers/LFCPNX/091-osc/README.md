# 091-osc: the internal oscillator (OSC_CORE) on LFCPNX-100

The oscillator is OSC_CORE_R1C137, in tile CIB_R0C137:EFB_1_OSC (the site Radiant placed OSCA at in
038-adc's designs). `fuzzer.py` runs LIFCL's 091-osc settings there with structural builds
(`osc_100.v`):
- words HF_CLK_DIV, HF_SED_SEC_DIV (8 bits each);
- enums DTR_EN, HF_FABRIC_EN, HF_OSC_EN, HFDIV_FABRIC_EN, LF_FABRIC_EN, LF_OUTPUT_EN, DEBUG_N.

All nine come out bit for bit the same as on LIFCL-40's EFB_1_OSC. As on LIFCL, the primitive alone
sets no bits, so there is no MODE enum.

LIFCL's 091 also fuzzes the oscillator's routing with lapie, which is not used here. The fabric
connections come from Radiant-routed designs instead:
- `timing/fuzzers/LFCPNX/17-osc-pins`: OSCA with HFOUTEN / HFSDSCEN from registers, HFCLKOUT and
  LFCLKOUT each clocking a register;
- `tools/radiant-fuzz/infer_edge_block_conns.py osc`.

Result, over 12 designs (every arc unanimous):

| Pin | Connection (EFB_1_OSC) | LIFCL-40 |
|---|---|---|
| HFOUTEN | `S1:JHFOUTEN_OSC_CORE <- S1W3:JCIBMUXOUTD3` | same |
| HFSDSCEN | `S1:JHFSDSCEN_OSC_CORE <- S1W3:JCIBMUXOUTC5` | same |
| HFCLKOUT | `G:JOSCHF_RMID_CORE_RMIDMUX <- S1:JHFCLKOUT_OSC_CORE` | TMID instead of RMID |
| LFCLKOUT | `G:JOSCLF_RMID_CORE_RMIDMUX <- S1:JLFCLKOUT_OSC_CORE` | TMID instead of RMID |

- **Clock outputs.** Their routes to the clocked registers are traced backward to where they start.
  - HFCLKOUT's always start at the right-side clock mux's oscillator input.
  - LFCLKOUT's start at its LF input, which appears on no HFCLKOUT arc. (Its arcs also show the HF
    input: the clocked register's CLK pin key covers both clock inputs of its slice.)
  - Radiant used RMID in every design; whether TMID is also connected is not known.
- **Trims.** HFTRMFAB / LFTRMFAB are not ports of OSCA. Radiant ties all 18 to one constant LUT
  output, so the arcs cannot tell them apart, and they get no connection here.
