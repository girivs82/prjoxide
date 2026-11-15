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

## Edge-clock connections (banks 3 / 4 / 5)

All of the HP-bank edge-clock wiring was checked against Radiant's routing. The checks use
`timing/fuzzers/LFCPNX/18-eclk-pins`: 18 designs with every ECLKSYNC and ECLKDIV of banks 3-5
pinned to its site, each ECLKSYNC fed from its own PCLK pin (random assignment), and every STOP /
DIVRST / SLIP on its own register. Runs 13-18 feed some banks' edge clocks from another bank through
the cascade inputs. Two architectural rules show in par's refusals:
- edge clock j of a bank carries only an index-j ECLKSYNC (its own or a cascaded one), and an
  ECLKSYNC always occupies its own bank's edge clock j;
- an edge clock drives at most one ECLKDIV.

**Fabric pins** (`tools/radiant-fuzz/infer_edge_block_conns.py eclksync / eclkdiv`): every pin is
unanimous over 14-18 arcs.

| Pin | Bank 3 | Bank 4 (new) | Bank 5 |
|---|---|---|---|
| ECLKSYNC STOP k=0..3 | N1:CIBMUXOUT D2 B4 B7 B5 | N1E1:CIBMUXOUT B2 D3 B1 B6 | N1E2:CIBMUXOUT D1 B3 D0 B0 |
| ECLKDIV DIVRST k=0..3 | N1E3:LSR0/1, N1E2:LSR0/1 | N1E2:LSR0/1, N1E1:LSR0/1 | N1E1:LSR0/1, N1:LSR0/1 |
| ECLKDIV SLIP k=0..3 | N1E1:CIBMUXOUT C2-C5 | N1E2:CIBMUXOUT C6 C7 D0 D1 | N1E3:CIBMUXOUT D2-D5 |
| ECLKDIV DIVOUT k | G:JECLKDIV<k>_BMIDMUX | G:JECLKDIV<4+k> | G:JECLKDIV<8+k> |

- Banks 3 and 5 confirm the LIFCL-derived entries exactly.
- DIVOUT is traced backward from the registers it clocks (`--clock-sink=CLK`). An IOLOGIC's SCLK pin
  key does not resolve to one route.

**Clock pins** (`tools/radiant-fuzz/check_eclk_routing.py`), read from the pips Radiant sets:
- **ECLKIN k <- G:JMUXIN<k>_ECLKBANK<b>, all three banks.**
  - With the balls assigned to ECLKSYNCs at random, each PCLK ball maps to one JPCLKT input in every
    design (14-18 designs each) only if ECLKSYNC k takes JMUXIN k.
  - Bank 3 balls AC12 / AB11 / Y5 / AB4 -> JPCLKT 0 / 1 / 2 / 3; bank 4 AD21 / AB19 / AA13 / AE13 -> 0 / 1 / 2 / 3;
    bank 5 V23 / W24 / AD25 / AC21 -> 0 / 1 / 2 / 3.
- **ECLKOUT k -> SYNCM k, and the cascade inputs.** These are read from the raw select bits.
  - A cascade mux's two select bits sit in two different tiles. Per tile, CAS0M or CAS1M shares its
    bit with SYNCM, so the per-tile decode can name the wrong input.
  - Own ECLKSYNC -> SYNCM k on all banks.
  - CASMUX3: CAS0M <- bank 5, CAS1M <- bank 4. CASMUX4: CAS0M <- bank 3, CAS1M <- bank 5.
    CASMUX5: CAS0M <- bank 4, CAS1M <- bank 3. As the database has them.
- **ECLKDIV ECLKIN k <- CASMUX output k.** Par accepts nothing else.
- **DDRDLL feeds.**
  - The right DDRDLL takes bank 3's edge-clock tree (CASMUX3), as in the database.
  - The left DDRDLL takes bank 4's (CASMUX4): with the DDRDLL on the left and the only edge-clock
    user, Radiant cascades even a bank-5 ECLKSYNC into CASMUX4. LIFCL's tree 0 (CASMUX5) connection
    for `G:JCLKOUT_ECLKDDRL_k` is replaced by tree 1, and DOSCL_P18's mux inputs `JECLKk_I0` are
    connected to it.
- **DQSBUF edge clock.** The bank-5 DQS0 tile type took its edge-clock inputs from bank 4's CASMUX4,
  copied from the bank-4 type. A bank-5 DQSBUF clocked from a bank-5 ECLKSYNC (DDRDLL on the right)
  uses CASMUX5 only, so they now come from CASMUX5.

`tools/radiant-fuzz/write_eclk_clock_conns.py` writes the clock-pin connections. The fabric pins are
written with `infer_edge_block_conns.py --write`.
