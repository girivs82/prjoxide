# 156-dqsw-iologic: IOLOGIC output gearing clocked by the DQSBUF (LFCPNX-100, bank 3)

`IOLOGICA.MODDRXN.DQSW_CLK` (first tile of a pad pair, F62B0) and `IOLOGICB.MODDRXN.DQSW_CLK`
(second tile, F63B0), options OFF / ON.

ON is set on every IOLOGIC whose output gearing is clocked by its DQS group's DQSBUF, the
MODDRXN modes:
- ODDRX4DQ on DQSW270 (DQ, DM);
- ODDRX4DQS on DQSW (DQS, or DM on DQSW).

It is set together with `MODDRXN.DDRMODE` MODDRX4_DQSW / MODDRX4_DQSW270. It is not set by:
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

Not covered: banks 4 and 5, and X2 gearing (MODDRX2_*).
