# 159-pll-refclk: pads into the PLL reference clock muxes (LFCPNX-100)

Each PLL's REFMUX has 16 inputs, JREFCLK10-17 and JREFCLK20-27. Their select bits were already in
the GPLL tile types. The fixed connections from pads into them, though, were LIFCL-40's, copied
over:
- **Wrong bel names:** LIFCL's `JPADDI_DIFFIO18_CORE_IOA`, where LFCPNX's HP banks have
  `JPADDI_DIFFIO18A_CORE_IOA`.
- **Wrong locations:** LIFCL-40's pad offsets, which mostly land on tiles with no pad.

So no pad reached a REFMUX in the routing graph, and the timing extractor could not trace
pad -> REFCK.

## Method

- **Pads:** the 28 true-side clock-capable pads of LFG672 (PCLKT* and *_GPLL*_IN, banks 1-7),
  listed by `pins.py`.
- **Designs:** for each PLL and pad, `gen.sh` makes a design with the PLL pinned at its site, REFCK
  from that pad, and CLKOP clocking a counter. That is 112 designs, built in the Radiant container
  (`radiant.sh`). The PLL wrapper is SKALP's (FBKCK = CLKOP) and is not published.
- **Reading the result:** `collect.sh` reads the REFMUX select from each decoded bitstream. It also
  checks par's report for whether the pad was put on a primary clock.
- **How a pad reaches the REFMUX:**
  - **On a primary clock:** the REFMUX takes JREFCLK21 (JCLK0 next to the PLL), or JREFCLK11 when
    the clock is routed on the local clock wire.
  - **Dedicated:** the select is one of the other inputs and the pad is not on a primary clock.
    That input is wired to the pad.

## Results

| PLL | REFCLK13 | REFCLK14 | REFCLK15 | REFCLK16 | REFCLK23 | REFCLK25 | REFCLK26 |
|---|---|---|---|---|---|---|---|
| LLC | PL42A (PCLKT6_0) | PB2A (LLC_GPLL0T_IN) | PB52A (PCLKT4_0) | PB4A (PCLKT5_0) | PL44A (PCLKT6_1) | PB58A (PCLKT4_1) | PB10A (PCLKT5_1) |
| LRC | PB112A (PCLKT3_0) | PB156A (LRC_GPLL0T_IN) | PB52A (PCLKT4_0) | PR42A (PCLKT2_0) | PB118A (PCLKT3_1) | PB58A (PCLKT4_1) | PR44A (PCLKT2_1) |
| ULC | PL31A (PCLKT7_0) | PL3A (ULC_GPLL0_IN) | | | PL29A (PCLKT7_1) | | |
| URC | PR31A (PCLKT1_0) | PR4A (URC_GPLL0_IN) | | | PR29A (PCLKT1_1) | | |

- **Shared pads:** the bank-4 pads PB52A and PB58A reach both bottom PLLs, on the same inputs
  (15, 25).
- **Other pads:** every other pad reached the PLL through a primary clock.
- **Database changes:** the GPLL tile types' pad connections are replaced by the table above, as
  `JPADDI_<DIFFIO18A|SEIO33>_CORE_IOA` of the pad's SYSIO tile. The JCLK0 inputs (11, 21) are kept.
- **Checks:** the designs decode with no unknown bits and pack back to the same FASM.

## Not covered

These GPLL connections are still LIFCL-40's, and their wires do not exist at the tile they point to:
- the ADC clock input (LRC / URC `JCLKDCLK_ADC_CORE_ADC0`);
- the SGMII CDR reference clock (LLC `JSREFCLK_SGMIICDR_CORE`);
- URC's `N1W1:JCLK0`.

The complement-side pads (PCLKC*, *_GPLL0C_IN) were not tried.
