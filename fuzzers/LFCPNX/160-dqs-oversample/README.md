# 160-dqs-oversample: plain IDDRX4 / IDDRX2 and DELAYA on a DQS pad (LFCPNX-100)

**Question:** can a DQS pad's input be oversampled in the FPGA by its own IOLOGIC, with plain
edge-clocked input gearing (IDDRX4 / IDDRX2, clocked by ECLK + SCLK, not the DQS-clocked
IDDRX4DQ), while the pad also feeds the DQS group's DQSBUF?

**Pads:** channel A lane 0's DQS, AF4 = PB150A (bank 3). Its IOLOGIC is IOLOGICA of R74C150,
SYSIO_B3_0_DQS1. The complement AF3 = PB150B is IOLOGICB of R74C151, SYSIO_B3_1_DQS2.

**Designs:** `gen.py <dir>` writes them. Each was built with `radiant.sh` (CLI flow, `bitgen
-ipeval`) and decoded.
- The base is the bank-3 byte-lane PHY of 156-dqsw-iologic:
  - DQSBUF_IVREF on the AF4 group (LPDDR4_BL16_EN, IVREFI = 49);
  - ECLKSYNC -> ECLKDIV /4 -> SCLK, and a DDRDLL;
  - LVSTL IO types;
  - 24-dqsbuf-pins run 2.
- The added IDDRX4 shares ECLK / SCLK. Its RST and ALIGNWD come from registers.

## Results

| Design | What it is | Result |
|---|---|---|
| a | bidir DQS with ODDRX4DQS + TSHX4DQS, DQSBUF, IDDRX4 on the DQS pad | **map refuses** (52331029 / 52281047: "Input DDR ... cannot be packed into IOC ... could conflict with other IO logic associated with the same IO port") |
| a4 | as a, tristate from the fabric (ODDRX4DQS only) | **map refuses**, the same error |
| a2 | input-only DQS (LVSTLD_I), DQSBUF, IDDRX4 on the DQS pad | builds, 0 unknown bits |
| a3 | IDDRX4 alone on AF4 | builds |
| x2 | IDDRX2 alone on AF4 (ECLKDIV /2) | builds |
| a2d | as a2, DELAYA between the pad and the IDDRX4, pad -> DQSI direct | **map refuses** (52331040: "Delay ... input signal ... cannot drive both delay component and other logic") |
| a2d2 | as a2d, the DELAYA output also on DQSI | **map refuses** (71003034: DQSI can only be driven by a pad's PADDI or an IOLOGIC's INCK, not by the delayed INDD) |
| a3d | DELAYA -> IDDRX4 alone on AF4 | builds |
| b | single-ended DQS on AF4 (LVSTL_I, bidir, ODDRX4DQS + TSHX4DQS, plain DQSBUF), IDDRX4 on AF3 as a separate LVSTL_I input | builds; the AF4 IOLOGIC and the DQSBUF are unchanged |
| b2 | as b, DELAYA -> IDDRX4 on AF3 | builds |

**Conclusions:**
- **One pad, DQSBUF and IDDRX4 together:** this works only if that pad's IOLOGIC has no output
  gearing. A bidirectional DQS with ODDRX4DQS (with or without TSHX4DQS) cannot also take input
  gearing.
- **DELAYA on that path:** DELAYA on a DQS pad that also feeds the DQSBUF is refused. The pad's
  input can feed either the delay line or other logic, but not both. DQSI cannot be fed from the
  delayed signal.
- **Complement pad:** IDDRX4, with or without DELAYA, works on the complement pad when the pair is
  split into single-ended pads.
  - **Caveat:** a bank's DQSBUF_IVREF needs an LVSTLD DQS pad (see 157-dqsbuf-ivref). With the
    pair split, the group cannot host it. Without a DQSBUF_IVREF somewhere in the bank, BANK<n>.IVREF
    stays off, and the bank's VREF_INT LVSTL inputs read 1 (see 037-ivref).

## Bits

All are already in the database (IDDRXN gearing, 070-iologic_mode, db 0fae1b3). The IOLOGIC of
the pad with the gearing gets:

| Setting | Value |
|---|---|
| `IDDRXN.DDRMODE` | `IDDRX4` or `IDDRX2` |
| `GSR` | `DISABLED` (the parameter) |
| `LSRINMUX` | `LSRIN` (RST) |
| `SCLKINMUX` | `SCLKIN` |

- Unlike IDDRX4DQ, there is no `MODE` or `MIDDRXN` setting.
- **With DELAYA**, on the same IOLOGIC, as on DQ pads:
  - `DELAY.COARSE_DELAY_MODE`, `DELAY.DEL_VALUE[6:0]`;
  - `INMUX.DELAY`;
  - `DIRMUX.DIR`, `LOAD_NMUX.LOAD_N`, `MOVEMUX.MOVE`;
  - `RANK0UPDATEMUX`, `RANK1UPDATEMUX`, `RANKENABLEMUX`, `RANKSELECTMUX`.
- **Pins** (IOLOGIC wires `J<pin>_IOLOGIC_CORE_I_GEARING_PIC_TOP_<A|B>`, as routed in a3):

| Port | Pin | Note |
|---|---|---|
| D | the pad | |
| ECLK | ECLK | |
| SCLK | SCLKIN | |
| RST | LSRIN | |
| ALIGNWD | WORDALIGN | from the CIB's CIBMUXOUTB1 |
| Q0-Q7 | RXDATA0-7 | |

`primitives.json` has IDDRX4 and IDDRX2 entries with these pins, timed by the `IOLOGIC:IDDRXN`
cell of cells_<grade>.json.
