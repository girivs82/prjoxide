# LFCPNX (CertusPro-NX) fuzzers

Ports of the LIFCL fuzzers to LFCPNX-100 (LFG672), run with Lattice Radiant
2026.1 (`tools/radiant-fuzz/` has the Docker runner). Builds use the
structural `sv2udb` path (`STRUCT_VER=1`) and, as for all LFCPNX-100 work in
this repo, readback bitstreams (`RBK_MODE=1`): with this Radiant, LFCPNX
bitstreams are only produced with `-ipeval`, which encrypts full bitstreams,
so only CRAM (no IP-bus writes) can be diffed.

## Provenance of the data

Two kinds of results come out of this work; keep them apart when reviewing.

**Pure bitstream diffs** (standard prjoxide method: vary one setting, diff CRAM):

| Fuzzer | Gives |
|---|---|
| `031-io_mode` | PIO enums for every SEIO33 SYSIO tile type (B0/B1/B2/B6/B7 EVEN/ODD, B1_DED, B1/B2/B6/B7 `_0_C` and `_0_REM`). Radiant 2026.1 rejects `INPUT_LVCMOS10` on SEIO33, so it is absent. |
| `032-hsio_mode` | PIO enums for the HP-bank SYSIO tile types (B3/B4/B5, incl. DQS/V18/ECLK variants). On LFCPNX the primitives are `SEIO18A_CORE`/`DIFFIO18A_CORE`. |
| `060-ebr-config`, `080-dsp-config` | EBR, MIB_EBR and DSP configuration bits. |
| `122-pll-config` | GPLL_{ULC,URC,LLC,LRC} enums (CLKMUX_FB, LMMICLK/LMMIRESETN inversion). LLC/LRC/ULC match LIFCL bit for bit; no MODE bit appears in the GPLL tiles on LFCPNX. |

The IO templates drive `PADDO` from a `VHI` because Radiant 2026.1 bitgen
refuses an undriven net (ERROR 67005003). `tools/radiant-fuzz/filter_route_bits.py`
strips any routing bits that could leak into PIO enums because of that;
`compare_with_lifcl.py` lists per tile which settings match LIFCL.

**Radiant-routed designs, confirmed on silicon** (not single-setting diffs):

- `GPLL_LLC` and `GPLL_URC` pips/conns: derived from LIFCL's GPLL tiles with
  `tools/radiant-fuzz/derive_gpll_tiles.py`, using Radiant's own place and
  route of small PLL designs at each corner (refclk from each dedicated pad,
  PLLRESET/STDBY/PLLPOWERDOWN_N from pins, LOCK out). On LFCPNX the LLC PLL's
  CIB ports sit one row lower than on LIFCL and its pad-fed REFCLKs come from
  different pads; URC is LRC mirrored north/south. ULC and LRC match LIFCL.
  All four corners were then shown to lock on an LFCPNX-100 Versa board.
- `LFCPNX-100/baseaddr.json`: PLL_{ULC,URC,LRC,LLC} (0x0E000000, 0x0E020000,
  0x0E040000, 0x0E060000) and EBR_WID0/1 (0x20000000, 0x20020000), confirmed
  on silicon. `100-ip-base` cannot find these from Radiant: the readback
  bitstreams it has to use carry no IP-bus writes.

`100-ip-base`, `121-pll-ipconfig` and `140-bram-init` are kept for reference
but cannot produce results with this Radiant for the reason above.

## Bitstream frame order, TAP frames and LRAM (silicon-verified 2026-11-14)

**Frame order.** Radiant writes LFCPNX configuration frames as the 32 IO frames
at 0x8000, then one linear `LSC_PROG_INCR_RTI` run over every frame from
address 0: the main array, then the 16 right-side IO frames, then the 16
left-side IO frames, then the 42 TAP frames. There is no separate write at
0x8020. prjoxide packs and unpacks this layout since f0a566f (linear write) and
d734fc3 (order past the main array: right IO, left IO, TAP). So:

- bitstreams packed before f0a566f wrote the TAP frames at 0x8020, which never
  took effect: every global clock branch stayed at its default;
- bitstreams packed with f0a566f (before d734fc3) had the TAP and left-IO frames
  swapped and are not usable;
- decodes made before d734fc3 showed left-IO data as unknown bits in the TAP
  tiles, and TAP data as left-IO bits.

The TAP model in the database (LIFCL-derived) is correct: Radiant's bitstreams
decode with no unknown TAP bits. Its settings now take effect for the first
time. The TAP A/B of 2026-11-13 was invalid, because those bits never reached
the chip. With d734fc3, an LRAM design clocked on spine 2 through the TAP
branches works on silicon.

**Readback images** (`RBK_MODE=1`) hold the 32 IO frames, then the same linear
run, but it stops after TAP frame 9. So they contain only TAP frames 0-9 of 42,
and TAP settings cannot be fuzzed from readback images.

**LRAM**, confirmed on an LFCPNX-100 Versa board:

- Init base addresses 0x2E200000 + k * 0x20000, k = 0..6 = R21C158, R41C158,
  R57C158, R1C90, R1C105, R1C110, R1C125 (LRAM_0..6). These were taken from
  Radiant's own bitstream (`LFCPNX-100/baseaddr.json`).
- The init layout is as on LIFCL: 81920 bytes per LRAM, written as 5-byte bus
  frames at bus addresses base + 0 and base + 0x8000. Unpack has stored these at
  logical byte addresses since e965752; before that it lost 8 KB per LRAM.
- DPS and BENA_N0-3 must be driven by a real constant-0 net, as Radiant does: a
  routed net from a LUT with INIT = 0. Left at the CIB default (VCC), every read
  returns zero. A slice left blank does not supply 0: LUT INIT bits are stored
  inverted, so a blank LUT outputs 1.
- The connections of the control, test and status pins (DPS, IGN, INITN,
  STDBYN, TBISTN, SCANRST, OEA, OEB, ERRDET, LRAMREADY) are in the database
  from fea45a2 on (`timing/fuzzers/LFCPNX/11-lram-core-pins`).

Nothing Radiant-generated (bitstreams, udb, IP generator output, logs) is
committed; only the derived database.
