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
| `036-hsio-vref` | LVSTL_I/II and LVSTLD_I/II on the HP banks (BASE_TYPE, DRIVE_LVSTL, TERMINATION_1V1, VREF_LVSTL), the referenced-standard slew rate (SLEWRATE_REF), and the LVSTL bank / chip bits (BANKREF, DOSCL_P18). Its README also documents the LFCPNX decode choices below. |
| `037-ivref` | The LVSTL internal input reference: `BANK<n>.IVREF` and the IVREF_CORE `IVREFI[6:0]` connections (DQSBUF_IVREF), from Radiant-built designs; see its README. |
| `040-speed` | `CHIP.SPEED` (PMU F11B0, High-Performance vs Low-Power), as LIFCL. |
| `060-ebr-config`, `080-dsp-config` | EBR, MIB_EBR and DSP configuration bits. |
| `090-sysconfig` | SYSCONFIG port enums (ldc_set_sysconfig). JTAG_PORT is a PMU bit that is on by default; its DISABLE option locks JTAG out (see its README). |
| `091-osc` | The internal oscillator (OSC_CORE, new tile type EFB_1_OSC), bit for bit as LIFCL. Its fabric connections come from Radiant-routed designs (`timing/fuzzers/LFCPNX/17-osc-pins`). |
| `131-config-ip` | MULTIBOOT (CONFIG_MULTIBOOT_CORE), through the synthesized flow; which configuration cores exist and can be reached on LFCPNX-100. |
| `154-ddrll` | The two DDRDLLs, and the left one's clock input (DOSCL_P18 mux, DDR40_ECLK_L feed). |
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

## HP-IO decode post-passes (LFCPNX only)

`libprjoxide/prjoxide/src/lfcpnx_decode.rs` runs after the per-tile decode of LFCPNX bitstreams. It
does two things, described in `036-hsio-vref/README.md`:

- Second-tile PIOA enums take the first tile's decode of PIOA, or NONE when PIOA is unused.
- Of the DRIVE_*, TERMINATION_* and SLEWRATE / SLEWRATE_REF variants, only those for the PIO's IO
  type are kept.

A feature is only relabelled to another matching option, or dropped when the remaining features
explain all of its set bits, so decoding and then packing gives the same bitstream. Options with
identical bits are listed in each enum's database description; the decoder emits the last one by
name. LIFCL and LFD2NX decoding is unchanged.

## DQSBUF bits from Radiant-built PHY designs (banks 3, 4 and 5)

Two bits that 153-dqsbuf's structural builds cannot set came from a Radiant-built LPDDR4-style
byte-lane PHY (DQSBUF, DDRDLL, ODDRX4DQ / IDDRX4DQ / TSHX4DQ, DELAYA). It was built once per DQSBUF
input: all fabric inputs tied to 0, then each one driven from a register in turn, plus DLLCODE tied
to 0.

- `DQSBUF.DLLCODE` (SYSIO_B3_0_DQS1 F45B1): set when DLLCODE comes from the right-side DDRDLL
  (DDRDLL_CORE_R72C158). It is clear both when DLLCODE is tied to 0 and when it comes from the
  left-side DDRDLL (DDRDLL_CORE_R68C1): the same bank 4 / 5 design built with the DDRDLL pinned to
  each side sets it on every DQS group only with the right one. No bit tells "left DDRDLL" from
  "tied to 0". The option keeps its name, DDRDLL.
- F52B1 in SYSIO_B3_0_DQS3 was first written as `DQSBUF.DQSI`, because it was set in every such
  design. It is not DQSI: it is the low bit of the DQSBUF's edge-clock input select, and every
  early design used edge clock 1. With the ECLKSYNC pinned to each edge clock, the select is
  - ECLK0: no bits;
  - ECLK1: F52B1;
  - ECLK2: F51B1;
  - ECLK3: both.

  It is the same in the DQS3 tile of the bank 3, 4, bank-4 middle and bank 5 groups. It is written
  as LIFCL's pips `N1W8:JECLKOUT_I_DQS_TOP_ECLK_ROUTING_MUX <- N1W8:JECLK<k>_I_...`, and the
  DQSI enum is removed.

None of the other inputs (RDCLKSEL, RDDIR, RDLOADN, READ, READMOVE, SELCLK, WRDIR, WRLOAD_N, WRLVDIR,
WRLVLOAD_N, WRLVMOVE, WRMOVE) has a bit of its own. The same two bits were seen in banks 4 and 5
(SYSIO_B4_0_DQS1 / _DQS3, SYSIO_B5_0_DQS1 / _DQS3, and the bank-4 middle group's
SYSIO_B4_0_DQS1_MID / _DQS3_MID) and are written there too (`153-dqsbuf/write_phy_bits.py`).

The DQSBUF's routing-mux and pin wires are named as in LIFCL (`N1W5:` from the DQS0 tile, 5 columns
left). On LFCPNX-100, sv2udb accepts `JECLKOUT_I_DQS_TOP_ECLK_ROUTING_MUX` only at the DQSBUF site's
column: 3 columns left of DQS0 in the normal groups (C146, C50, C2) and 1 in the middle group (C62).
The names are labels in the database's graph (no bits depend on them), so they are left as they are.

Bank 4's middle DQS group (tile types SYSIO_B4_*_DQS<k>_MID, C63-C67) is a group of its own: its
DQS pad is PB66A (AF21), not PB64A, and its DQSBUFA is DQSBUFA_CORE_R73C62 (one column left of its
DQS0 tile, where the other groups' sites are three columns left). Its DQSBUF settings are in the same
places as in the other groups' five tiles (153-dqsbuf, group DQSB4M).

F62B0 (first tile) / F63B0 (second tile) of every DQS-group IOLOGIC whose output is clocked by
DQSW or DQSW270 is `IOLOGIC<x>.MODDRXN.DQSW_CLK`, from the same PHY designs; see
`156-dqsw-iologic/README.md`. With it, and with the static bits of 170-mpcs-serdes recorded as
always_on, these PHY designs decode with no unknown bits. When Radiant places the DDRDLL on the left,
its clock input is decoded too: the DOSCL_P18 CLKIN mux and the DDR40_ECLK_L edge-clock feed
(`154-ddrll/README.md`).

