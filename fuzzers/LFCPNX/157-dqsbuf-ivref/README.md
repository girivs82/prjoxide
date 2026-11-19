# 157-dqsbuf-ivref: DQSBUF_IVREF, OUTDELAYA and the PLL_LLC CLKOP feedback (LFCPNX-100)

Lattice's free LPDDR4 Memory Interface Module (Radiant IP Modules, FPGA-IPUG-02154) sets bits that the
database did not know. A Radiant build of it, decoded, had two kinds of unknown bits:
- `SYSIO_B3_1_DQS0` F55B1, in both DQS groups;
- F33B1 and F35B1-F39B1, in every bank-3 IO tile that held a DQ, DMI or DQS pad.

A SKALP-exported PHY with the PLL feedback fixed had a third kind: `BMID_0_ECLK_1` F79B1-F82B1.

This fuzzer names all three. With them in the database:
- the module build decodes with no unknown bits outside the PLL IP-bus writes;
- the PHY decodes with none either;
- both pack back to the same FASM.

## Method

- **Designs:** `timing/fuzzers/LFCPNX/12-dqsbuf-ivref/gen_dqsbuf_ivref.py` generates them; options
  added for this fuzzer are listed in the script.
  - Each DQS group has a DQSBUF or DQSBUF_IVREF, a DQS bidir on ODDRX4DQS / TSHX4DQS, and DQ bidirs on
    ODDRX4DQ / TSHX4DQ / IDDRX4DQ.
  - Every fabric input comes from its own register.
- **Build:** `build.sh <name> VAR=value ...` writes the design, builds it in the Radiant container (CLI
  flow: LSE, map, par, `bitgen -ipeval`) and decodes it.
- **Writing:** `write_db.py` writes the bits and `write_primitives.py` updates `primitives.json`.
  Both are no-ops when re-run.

The builds (group 0: bank-3 DQS AF4; group 1: bank-4 AF22; group 2: bank-5 U26 unless noted):

| Build | Varies | Result |
|---|---|---|
| base | 3 x DQSBUF_IVREF, defaults | no unknown bits |
| bl16en / bl16dis | LPDDR4_BL16_EN = ENABLED / DISABLED | ENABLED: F55B1 in each group's DQS0 tile (C149, C53, C5); DISABLED = base |
| af6_bl16 | bank-3 group at AF6 | F55B1 in that group's DQS0 tile, C137 |
| mid_bl16 | bank 4's middle group (AF21) | F55B1 in SYSIO_B4_1_DQS0_MID, C63 |
| plain_bl16 | LPDDR4_BL16_EN on plain DQSBUF | LSE: "module DQSBUF does not have a parameter named LPDDR4_BL16_EN" |
| allp_ivref / allp_dqsbuf | every other DQSBUF parameter at a non-default value, on DQSBUF_IVREF / DQSBUF | identical DQSBUF bits; the only difference is BANK<n>.IVREF.ON |
| odly_en / odly_dis | OUTDELAYA on DQS and DQ, MARGIN_TEST_ENABLE = ENABLED / DISABLED | per pad: ENABLED F33 F35 F36 F37 F38 F39 B1; DISABLED F37 F38 F39 B1 |
| od_const | OUTDELAYA with LOAD_N / MOVE / DIRECTION tied off | the same as odly_en |
| od_d / od_t | only data, or only tristate, through the OUTDELAYA | map refuses both (see below) |
| cov_en / cov_dis / cov_ii | 26 pads on 20 more IO tile types (MID, ECLK_R, V18, DQS2-4, ...), DQS single-ended, plain DQSBUF; cov_ii with LVSTL_II DQs | the same bits on every tile type, for LVSTL_I and LVSTL_II |

The PLL feedback builds are minimal designs: PLL_LLC from the 125 MHz pin, with CLKOP -> ECLKSYNC ->
ECLKDIV -> a counter. Their sources are SKALP's PLL wrapper and are not published.

| Build | Varies | Result |
|---|---|---|
| a | FBKCK = CLKOP, CLKOP to an ECLKSYNC (bank 3 eclk 1) | FBKMUX JFBKCLK10; BMID_0_ECLK_1 F79-F82 B1 |
| b | FBKCK unconnected | FBKMUX JFBKCLK11 (GND on a primary clock); no F79-F82 |
| c | FBKCK = CLKOP, CLKOP to fabric only (primary clock) | FBKMUX JFBKCLK11; no F79-F82 |
| d / e | as a, ECLKSYNC pinned to bank 4 eclk 2 / bank 5 eclk 3 | F79-F82 B1 as in a |

## Bits

**DQSBUF.LPDDR4_BL16_EN** (DISABLED / ENABLED = F55B1):
- written to SYSIO_B3/B4/B5_1_DQS0 and SYSIO_B4_1_DQS0_MID;
- the DQSBUF_IVREF parameter for LPDDR4 burst length 16;
- Lattice's module sets it.

**DQSBUF_IVREF vs DQSBUF:**
- DQSBUF_IVREF is DQSBUF plus the bank's VREF generator (IVREF_CORE):
  - the extra input bus IVREFI[6:0], whose connections are in 037-ivref;
  - the extra parameter LPDDR4_BL16_EN.
- Every other parameter sets the same bits on both.
- It also sets BANK<n>.IVREF.ON, and Radiant then gives the bank's LVSTL inputs VREF_INT.
- Map places at most one per bank, and requires the group's DQS pad to be LVSTLD:
  "Port ... is controlled by IVREF and is DQS port, IO type cannot be 'LVSTL_I'".
- Port list (from the module's generated instance and LSE's netlist): DQSBUF's ports plus IVREFI[6:0].
  - Lattice's public Libraries Reference Guide could not be fetched here.
- No other port differs, so the only new routing is IVREFI, done in 037-ivref.
- In these netlist-level builds, S_READ / S_WRITE / SIGN_READ / SIGN_WRITE set no bits on either
  primitive. 153-dqsbuf found their bits at the bel level.

**IOLOGIC\<A|B\>.OUTDELAYA** (NONE / USED = F37B1 F38B1 F39B1) and
**IOLOGIC\<A|B\>.OUTDELAYA.MARGIN_TEST_ENABLE** (DISABLED / ENABLED = F33B1 F35B1 F36B1):
- Written to all 33 SYSIO_B3/B4/B5 tile types; each holds one pad (`_0`: PIOA / IOLOGICA,
  `_1`: PIOB / IOLOGICB).
- The bits are the OUTDELAYA primitive, which Lattice's module puts on every DQ, DMI and DQS output.
  It sits between ODDRX4DQ(S) / TSHX4DQ(S) and the pad, and its delay is adjusted by the
  LOAD_N / MOVE / DIRECTION_LPDDR4_WT pins (write training).
- **Data and tristate together only:** map accepts the OUTDELAYA only with both data and tristate
  through it. With data only it rejects the tristate path: "The PADDT port ... can either drive the
  TOUT port of SIOLOGIC_CORE or the TOUT port of IOLOGIC_CORE". With tristate only: "OUTDELAYA ...
  usage is wrong. It only can delay an output memory DDR". So F37-F39 cannot be split further with
  Radiant.
- **Overlap:** in the `_1` tile types, PIOA.DIFFIO18.BASE_TYPE's LVSTLD options (the complement
  side of a differential pad) also use F37B1 and F38B1. They never use F39B1, so the two do not
  decode as each other.
- **Training pins:** the fabric wires of LOAD_N / MOVE / DIRECTION / COUT_LPDDR4_WT were not fuzzed.

**BMID.LLC_PLL_FBK** (OFF / CLKOP = F79B1 F80B1 F81B1 F82B1, in BMID_0_ECLK_1):
- PLL_LLC's dedicated feedback from CLKOP into its FBKMUX input JFBKCLK10, which has no fabric
  connection in the database.
- Radiant uses it when FBKCK = CLKOP (internal-feedback mode, SEL_FBK = DIVA) and CLKOP is not on a
  primary clock, for example when CLKOP drives an ECLKSYNC on any bank's edge clock.
- When CLKOP is a primary clock, the feedback goes through JFBKCLK11 (global JCLK1) and these bits
  stay clear.
- The other three PLLs' equivalents were not checked.

## Not covered

- **LVSTL_II side finding:** DQ pads of LVSTL_II also set unknown bank-reference bits:
  - BANKREF3_DDR42 F13B1;
  - BANKREF4_DLY42_DDR41 F18B0;
  - BANKREF5 F18B0.
  They are left unnamed.
