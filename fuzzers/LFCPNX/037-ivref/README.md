# 037-ivref: the LVSTL internal input reference (bank VREF generator, LFCPNX-100)

An LVSTL input's `VREF=VREF_INT` (036's `VREF_LVSTL`) selects an internal reference, but the
reference's level comes from a separate block, IVREF_CORE ("BNKVRGEN18"). That block is used through
the `DQSBUF_IVREF` primitive, a DQSBUF with an extra 7-bit fabric input `IVREFI[6:0]`. Lattice's
LPDDR4 Memory Interface Module user guide (FPGA-IPUG-02154, section 2.4.9 and the port table)
drives that input from `dqs_grp_vref_i[6:0]`. The LPDDR4 controller guide (FPGA-IPUG-02127) calls
the same value "Initial MC DQ_VREF Value": range 0-127, default 49, translated to the internal
reference, and swept at runtime by read VREF training.

Without a DQSBUF_IVREF, nothing sets the reference level. LVSTL inputs then read 1 whatever the pin
does. This was seen on a Versa board with both Radiant's and SKALP's bitstreams, even while the
FPGA itself drove the pad low.

## What Radiant does (CLI flow builds)

- `DQSBUF_IVREF` maps to a DQSBUFA_CORE plus an IVREF_CORE (instance `<name>.BNKVRGEN18_inst`).
  Map requires the DQS port of that group to be an LVSTL type ("Port dqs_pad is controlled by IVREF
  and is DQS port, IO type cannot be 'HSUL12D'").
- One per bank. Par places at most one DQSBUF_IVREF in a bank: two in bank 3 fail placement, and
  one DQSBUF_IVREF with one plain DQSBUF in the same bank places. The IVREF pins take the same
  wires whichever DQS group of the bank uses it, so IVREF_CORE is a bank-level block.
- `BANK<n>.IVREF` (OFF / ON), set whenever the bank's IVREF is used. It is the same for
  IVREFI = 0, 49 or register-driven, so it says nothing about the level:
  - bank 3: BANKREF3_DDR42 F5B8 + F6B8;
  - bank 4: BANKREF4_DLY42_DDR41 F31B1 + F32B1;
  - bank 5: DDR40_ECLK_L (R74C14) F31B1 + F32B1.
- The level is routing. `IVREFI<k>` (k = 0..6) is driven from the CIBMUX wire C<k> next to the
  bank's reference tile. The connections are in that tile type, with the pin wires
  `JIVREFI<k>_IVREF_CORE`:
  - bank 3: BANKREF3_DDR42 (R73C159) `JIVREFI<k>_IVREF_CORE <- W1:JCIBMUXOUTC<k>`, i.e.
    R73C158;
  - bank 4: BANKREF4_DLY42_DDR41 (R74C77) `<- N1:JCIBMUXOUTC<k>`, i.e. R73C77;
  - bank 5: DDR40_ECLK_L (R74C14) `<- N1:JCIBMUXOUTC<k>`, i.e. R73C14.

  Every pin is unanimous over 5-6 arcs of six designs, three banks each, with the bank-3 group
  varying.

To use the internal reference, a design needs, per bank with LVSTL inputs:
- one DQSBUF_IVREF;
- IVREFI driven to the wanted level (constant or trained);
- `BANK<n>.IVREF.ON`;
- `VREF_LVSTL.VREF_INT` on the inputs.

## Method

- Probes: phy1 (156-dqsw-iologic) with DQSBUF_IVREF, LVSTL IO types, and IVREFI = 0 / 49 /
  register-driven. Single- and multi-bank builds from
  `timing/fuzzers/LFCPNX/12-dqsbuf-ivref/gen_dqsbuf_ivref.py` (`GROUPS=...`).
- Connections: timing fuzzer `timing/fuzzers/LFCPNX/12-dqsbuf-ivref`. Every DQSBUF_IVREF input is
  driven by its own register, there is one DQSBUF_IVREF per bank (3, 4, 5), and the bank-3 group
  is chosen at random. Then `tools/radiant-fuzz/infer_dqsbuf_conns.py --vote --write`, the
  LRAM-pin method of infer_block_conns.py.
- `write_db.py`: BANK<n>.IVREF. It creates nothing else; the DDR40_ECLK_L tile type file was
  created for the connections.

## DQSBUFA input connections (replaced)

The DQSBUFA input connections in SYSIO_B3/B4/B5_1_DQS0 came from LIFCL. Radiant's routing
contradicts all 21 fabric inputs: RDCLKSEL0-3, RDDIR, RDLOADN, READ0-3, READMOVE, SELCLK, WRDIR,
WRLOAD_N, WRLVDIR, WRLVLOAD_N, WRLVMOVE, WRMOVE, PAUSE, RST and RSTSMCNT. For example, RDDIR was
`N1E2:JCIBMUXOUTD2` and is `N1W3:JCIBMUXOUTD7`.

They are replaced with the inferred wires (`infer_dqsbuf_conns.py --replace`), the same on banks 3, 4
and 5. Every pin is unanimous over 12 arcs (12 designs of 12-dqsbuf-ivref, one group per bank each),
and no two pins share a source wire.

Check on other designs: timing/fuzzers/LFCPNX/13-dqsbuf-phy-check puts the bank-3 PHY of
156-dqsw-iologic (phy1 and four lane-moved variants) through the same flow. `--check` on those
5 designs alone gives the same wire for 20 pins (5 arcs each). For RST, which in that PHY shares its
net with every IOLOGIC reset, the trace leaves 9 LSR candidates; the new wire is among them, so
nothing contradicts it.

The outputs to the fabric were checked the same way. The trace runs backward from the capturing
register to where the route starts near the block, ignoring the database's own pin connections.
Each output drives a JQ7_CIBTEST wire of its own, unanimous over 12 arcs on banks 3, 4 and 5,
and the same on all 5 PHY designs (5 arcs each):

| Output | Drives |
|---|---|
| BTDETECT | `N1:JQ7_CIBTEST` |
| BURSTDETECT | `N1E1:JQ7_CIBTEST` |
| READCOUT | `N1E2:JQ7_CIBTEST` |
| DQSWRD | `N1E3:JQ7_CIBTEST` |
| DATAVALID | `N1E4:JQ7_CIBTEST` |
| WRCOUT | `N1E6:JQ7_CIBTEST` |
| WRLVCOUT | `N1W1:JQ7_CIBTEST` |

These replace LIFCL's JQ6 / JQ7 targets. The DQS-clock outputs to the fabric (SR90CIB, SW270CIB,
DQSWCIB) keep LIFCL's connections: no design drives fabric from them, so they are unchecked.
RDPNTR / WRPNTR have no fabric connections; they reach the IDDRX4DQ through dedicated paths.

## Not resolved here

- Bank 5, in a bank-5-only design: DOSCL_P18 F9B0 / F11B0 and DDR40_ECLK_L F102B1. These are
  probably the left DDRDLL / edge-clock path.
