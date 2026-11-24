# 156-dqsw-iologic: IOLOGIC output gearing clocked by the DQSBUF (LFCPNX-100, banks 3, 4 and 5)

`IOLOGICA.MODDRXN.DQSW_CLK` (first tile of a pad pair, F62B0) and `IOLOGICB.MODDRXN.DQSW_CLK`
(second tile, F63B0), options OFF / ON.

ON is set on every IOLOGIC whose output gearing is clocked by its DQS group's DQSBUF, the
MODDRXN modes:
- ODDRX4DQ on DQSW270 (DQ, DM);
- ODDRX4DQS on DQSW (DQS, or DM on DQSW).

It is set together with `MODDRXN.DDRMODE` MODDRX4_DQSW / MODDRX4_DQSW270, and in X2 gearing
(ODDRX2DQ / ODDRX2DQS) the same way with MODDRX2_DQSW / MODDRX2_DQSW270. It is not set by:
- a plain ODDRX4;
- TSHX4DQ or TSHX4DQS alone;
- input gearing (IDDRX4DQ);
- an unused pad.

070-iologic_mode's MODDRXN builds are structural, with no DQSBUF connected, so they never set it.
That is why it showed as unknown on every write-path pin of a Radiant-built PHY.

## Method

`phy1.v` / `phy1.pdc` / `phy1.sdc` is a byte-lane PHY test design built from base primitives:
- DQSBUF, DDRDLL, ECLKSYNC / ECLKDIV;
- ODDRX4DQ / TSHX4DQ / DELAYA / IDDRX4DQ on 8 DQ;
- ODDRX4DQ on DM;
- ODDRX4DQS / TSHX4DQS on DQS;
- ODDRX4 + DELAYB on CA.

`gen_variants.py <dir>` writes the variants. They are built with the radiant.sh CLI flow (LSE, map,
par, `bitgen -ipeval -d -w`) and decoded with `prjoxide unpack`:

| variant | change | DQSW_CLK on |
|---|---|---|
| phy1, g_notsh | (TSHX4DQ removed) | every DQ, DM and DQS IOLOGIC |
| p_dm_plain | DM on a plain ODDRX4 | not on DM |
| p_dm_dqsw | DM on ODDRX4DQS / DQSW | on DM |
| p_dq_tshonly | DQ without output gearing, TSHX4DQ only | not on DQ |
| p_dqs_tshonly | DQS without ODDRX4DQS, TSHX4DQS only | not on DQS |
| v_dm_af3, v_chb_hi, v_cha_hi | DM / byte lane moved to other pads and groups | tile-type coverage |

It was seen with the same bit on every bank-3 tile type that holds an IOLOGIC in a DQS group:
- IOLOGICA in SYSIO_B3_0, _0_DQS1 and _0_DQS3;
- IOLOGICB in SYSIO_B3_1, _1_DQS0, _1_DQS2, _1_DQS4, _1_V18, _1_V18_32 and _1_ECLK_R.

`write_db.py` writes the enum. It is a new enum only, so existing FASM packs unchanged.

## Banks 4 and 5, and X2 gearing

The designs come from the DQSBUF generator
`timing/fuzzers/LFCPNX/12-dqsbuf-ivref/gen_dqsbuf_ivref.py`, with plain DQSBUFs (`GROUPS=...`):
- with differential DQS, DQ pads on every bank 4 / 5 tile type: groups PB54 (AF22), PB66 (AF21,
  the bank-4 middle group), PB102 (AF14), PB6 (U26) and PB42 (AE26);
- with `DQS_SE=1` (single-ended DQS), a DQ on the DQS complement pad of groups PB54, PB66 and PB6;
- the first again with the DDRDLL pinned to the right side (`ldc_set_location -site
  {DDRDLL_CORE_R72C158} [get_cells u_dll.DDRDLL_inst]`);
- `GEAR=X2`: X2 gearing on a group of each of banks 3 (AF4), 4 (AF22) and 5 (U26).

A pad PB<n>A is in the tile at column n (PIOA), PB<n>B in the one at column n + 1 (PIOB). The bit is
set on every DQ / DQS pad, F62B0 in the first-tile types and F63B0 in the second-tile ones, and on
no other pad. It is written to all bank 4 / 5 tile types:
- IOLOGICA: SYSIO_B4_0, _0_DQS1, _0_DQS3, _0_DQS1_MID, _0_DQS3_MID; SYSIO_B5_0, _0_DQS1, _0_DQS3;
- IOLOGICB: SYSIO_B4_1, _1_DQS0, _1_DQS2, _1_DQS4, _1_V18, _1_V18_42, _1_DQS0_MID, _1_DQS2_MID,
  _1_DQS4_MID; SYSIO_B5_1, _1_DQS0, _1_DQS2, _1_DQS4, _1_V18, _1_V18_51.

The X2 design decodes with no unknown bits at all. Its MODDRX2_* / MIDDRX2 / IDDRX2 options come
from 070's structural builds, and DQSW_CLK is set as in X4. With the database written, the bank 4 / 5
designs have no unknown bits in any SYSIO tile. With the DDRDLL on the left, three more bits were
set outside the SYSIO tiles: DOSCL_P18 F9B0 / F11B0 and DDR40_ECLK_L F102B1. They are the left
DDRDLL's clock input (`154-ddrll/README.md`). With those written, these designs have no unknown bits.
