# 038-adc: the ADC (ADC_CORE) on LFCPNX-100

Configuration bits and fabric connections of the hard ADC: site ADC_CORE_R68C158, tile
CIB_R68C159:ADC. No IP licence is needed (a base primitive, like the PLL).

## What Radiant requires

- Performance grade 8 or 9. Grade 7, radiant.sh's default, is refused: "ADC ... is not supported
  for current performance grade". The Versa board's part is -9.
- The industrial operating condition. Commercial is refused. radiant.sh passes `OPER_COND` to
  postsyn as `-oc`; builds that set it bypass the bitstream cache, whose key does not include it.
- CLKDCLK "can only be driven by the CLKOS4 port of PLL_CORE", and par wants that PLL to be
  PLL_LRC. Its reference can come from the LRC input pad (AD21), the global clock network (a
  fabric clock pin) or the internal oscillator (OSCA); all three map and par. An ADC with CLKFAB
  only (CLKDCLK open) also maps and pars. Whether it converts that way is not known.
- The analog inputs are not ports of LSE's ADC primitive. A pad reaches the ADC through its own
  `ENADC_IN=ENABLED` (032's `PIO<x>.SEIO18.ENADC_IN`). The channel is chosen at runtime by the
  fabric ports CHASEL[3:0] / CHBSEL[3:0], so the code-to-pad map is not in the bitstream.

From Lattice's ADC user guide (FPGA-TN-02129), as passed on from the LPDDR4 work and not checked
here: ADC1 channel codes 0-7 select CP8-15 / CN8-15 (e.g. CP14 / CN14 = ADC1 code 6); the
conversion clock is the LRC PLL's CLKOS4 divided by CLK_DIV, at most 25 MHz; the fabric clock
(CLKFAB) at most 40 MHz.

## Configuration (fuzzer.py; enums and a word in tile type ADC)

One parameter at a time against the instance with all parameters unset. Legal values are from
map's errors. Every option lists all the bits of its enum.

| Parameter | Values (default first) | Bits |
|---|---|---|
| ADC_ENP | ENABLED, DISABLED | F5B0 |
| EN_COMP1 / 2 / 3 | ENABLED, DISABLED | F11B1 / F10B1 / F7B1 |
| REFBUFAEN / REFBUFBEN | ENABLED, DISABLED | F6B1 / F5B1 |
| VREFASEL / VREFBSEL | INTERNAL, EXTERNAL | F14B2 / F10B2 (set = INTERNAL) |
| CTLCOMPSW1 / 2 / 3 | DISABLED, ENABLED | F4B0 / F3B0 / F0B0 |
| DF | STRAIGHT_BINARY, TWOS_COMPLEMENT | F12B1 |
| OMA / OMB | BIPOLAR, UNIPOLAR | F15B1 / F14B1 |
| SLEEP | DISABLED, ENABLED | F3B1 |
| VREFACFG | 1P0_TO_1P2, 1P2_TO_1P4, 1P4_TO_1P6, 1P6_TO_1P8 | F2B1 / F1B1 (binary) |
| VREFBCFG | as VREFACFG | F13B2 / F12B2 |
| CLK_DIV | 0-255, default 2 | word: F8B2 F5B2 F4B2 F3B2 F1B2 F0B2 F15B3 F13B3 (bit 0 first) |

An ADC instance has no bits of its own beyond these defaults, so there is no MODE enum. FASM for
an ADC lists its parameters, defaults included.

## Fabric connections (timing/fuzzers/LFCPNX/15-adc-pins)

The method is `tools/radiant-fuzz/infer_adc_conns.py`, as for the LRAM / DQSBUF pins. Twelve
Radiant-routed designs drive every input from its own register and capture every output. A pin
is written only when one wire is left and all of at least 10 arcs agree.

- **All 52 fabric pins connected.** The 48 traced fabric pins, plus CHBSEL3, CLKFAB, RSVDH and RSVDL, are written to
  the ADC tile type as `W1:J<pin>_ADC_CORE_ADC0` (LIFCL's naming).
  - Inputs come from CIBMUXOUT / CE wires next to the block; e.g. CHASEL0-3 <- S1W1:JCIBMUXOUTA0-3,
    CHBSEL0-3 <- S1W1:JCIBMUXOUTA4-7.
  - Outputs enter the CIB at JF / JQ *_CIBTEST wires; e.g. DA0-6 -> W1:JF0-6_CIBTEST,
    DB3-6 -> W1:JQ3-6_CIBTEST.
- Two batches of 12 designs (runs 1-12, 13-24):
  - 46 pins are unanimous over all 24 arcs.
  - CHASEL2, CHASEL3 and CHBSEL3 are unanimous within one batch of 12 and have one dissenting arc
    in the other: 23/24, 22/23 and 23/24. Their A-wires often have no explicit pip (the CIBMUX
    takes its zero-bit default), so the dissent is most likely a tracing artifact. All three
    follow the regular A0-A7 pattern and agree with LIFCL.
- CLKFAB is a clock, so it has no SDF arc. Its connection is read from the routing: every design
  feeds it through the clock-branch pip into R69C158 JCLK0, i.e. `W1:JCLKFAB_ADC_CORE_ADC0 <-
  S1W1:JCLK0` (the same as LIFCL). That is the same wire for a pin clock (all 24 runs), the internal
  oscillator and a PLL_LRC output; only the branch feeding JCLK0 differs.
- 47 agree with LIFCL. The 3 that do not are COMP1O / COMP2O / COMP3O: S2W1:JF0/1/2_CIBTEST here,
  N2W1:JQ0/1/2 in LIFCL.
- **RSVDH / RSVDL** are fabric inputs that LSE's ADC primitive does not expose. Radiant ties both
  to **0**: GND_net in the backannotated netlist, one constant LUT output, in all 24 designs. They
  enter on R69C158 JCIBMUXOUTC0 / C1: `W1:JRSVDH_ADC_CORE_ADC0 <- S1W1:JCIBMUXOUTC0`, `W1:JRSVDL_...
  <- S1W1:JCIBMUXOUTC1`.
  - `tools/radiant-fuzz/check_adc_rsvd.py`: in every design both wires carry that one net and no
    other ADC input.
  - Which wire is H and which L cannot be told apart in Radiant's designs (same net). The
    assignment follows LIFCL; both must be 0 anyway.
  - A design has to drive them low. Left unconnected, a CIB input reads 1, and the ADC then
    converts at mid-scale (seen on a Versa board; driving both low gives Radiant's readings).
  - `LFCPNX/tied_inputs.json` in the database records this.
- No other ADC_CORE fabric input is tied by Radiant. The others (ADCEN, CAL, CHAEN, CHASEL0-3,
  CHBEN, CHBSEL0-3, CLKFAB, CONVSTOP, RESETN, RSTN, SOC) are primitive ports. The remaining
  ADC_CORE inputs are analog or dedicated (GPIOP / N, DP / DN, COMP*IP / IN, CLKDCLK).

## Analog inputs on the Versa board

Each ball's ADC_CP<k> / ADC_CN<k> name is from the board schematic (FPGA-EB-02053, Figures
A.5 / A.7). CP is the pair's A pad, CN the B pad.

| k | CP / CN balls | Site | Versa net |
|---|---|---|---|
| 0 | V24 / V23 | PB2 | bank 5 (SFP3 RX); also COMP1 |
| 1 | -- | PB4 | bank 5; also COMP2 |
| 2 | -- | PB10 | bank 5; also COMP3 |
| 3 | -- | PB8 | bank 5 |
| 4 | AC12 / AD12 | PB112 | LPDDR4 UDM_B / DQ9_B |
| 5 | W13 / Y13 | PB98 | LPDDR4 RESET_N / - |
| 6 | AF14 / AF13 | PB102 | - |
| 7 | AA13 / AB13 | PB100 | LPDDR4 CK_t / CK_c |
| 8 | AD11 / AE11 | PB116 | LPDDR4 DQ10_B / DQ11_B |
| 9 | AC13 / AD13 | PB104 | - |
| 10 | AA12 / AB12 | PB110 | LPDDR4 DQ15_B (VREF3_1) / DQ12_B |
| 11 | AF4 / AF3 | PB150 | LPDDR4 DQS0_t_A / DQS0_c_A |
| 12 | AD4 / AE4 | PB152 | LPDDR4 DQ5_A / DQ4_A (schematic) |
| 13 | Y11 / AA11 | PB120 | LPDDR4 DQ14_B / DQ13_B |
| 14 | Y6 / AA6 | PB146 | LPDDR4 DQ2_A / DQ0_A |
| 15 | AB4 / AC4 | PB154 | - / LPDDR4 DQ7_A |

The dedicated inputs: ADC_DP0 / DN0 go to the potentiometer by default (jumpers J25 / J26), and
can be switched to header J27. ADC_DP1 / DN1 are AE1 / AD1 on header J27 (pins 9 / 11).
ADC_REFP0 / REFP1 take the board's ADC_Vref by default (J28 / J29).

The CHASEL / CHBSEL code for each input is not in the bitstream. Code k for GPIO k (e.g. 10 for
ADC_CP10) is the likely candidate but needs a board test.

## The bank reference and the ADC

- No setting routes a bank's internal LVSTL reference (IVREF) to the ADC or to a pad.
- `IO_TYPE=VREF1_DRIVER` on a VREF pad (AA12, VREF3_1) is accepted only on an input port, and
  only in a bank whose VCCIO allows it. Map refuses it in an LVSTL bank, with or without
  DQSBUF_IVREF: "In the bank [3], VCCIO for [vref1] is incompatible with port [dqs0]".
- In an SSTL bank it sets PIOA.SEIO18.VREF1_DRIVER.ON and BANK3.REF_IO.ON: the bank's external
  VREF generator, not IVREF.
