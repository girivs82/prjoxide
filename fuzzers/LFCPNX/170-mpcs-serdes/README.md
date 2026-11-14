# 170-mpcs-serdes: LFCPNX SERDES (MPCS / PCSX) configuration

Maps the CertusPro-NX SERDES lane configuration: the IP-bus register block of each PCS lane, and the
lane / quad / bonding bits in the `PCS_0`..`PCS_7` tiles. Everything is derived from Radiant 2026.1
builds that use only the MPCS module shipped with Radiant (`ip/lifcl/mpcs`) and the PCSX1/PCSX4 hard
primitives it instantiates, built with the CLI flow (LSE, map, par, `bitgen -ipeval -d -w`; plain
bitstreams, no licence feature needed). Nothing Radiant-generated is committed; the scripts regenerate it.

## Results (written by `write_db.py`)

- `LFCPNX-100/baseaddr.json`: `PCS_LANE0`..`PCS_LANE7` at `0x0E420000 + lane * 0x20000` (abits 9).
  Lanes 0-3 are quad 0 (`PCS_0`..`PCS_3` tiles), lanes 4-7 quad 1.
- `iptypes/PCS_LANE.ron` (IP type for `IP_PCS_LANE<n>` FASM features), one lane's registers
  (offsets 0x000-0x1E8), named after the PCSX1 attributes:
  - 248 words: the binary attributes (1709 of 1712 bits; `HINT` has no register effect);
  - 192 enums: the string attributes with a register effect, every option listing all of its bits
    explicitly. 0x1E1 bits 3-4 are shared by two enums and combine as OR in Radiant's output, so
    for those bits options only set;
  - `always_on`: register bits no attribute drives, with their value (and so the defaults of the
    other bits in each written byte). `Chip::configure_ip` applies them first.
  For a PCSX4 (multi-lane) instance, attributes `CH<k>_<name>` belong to lane k.
- `tiletypes/PCS_<n>.ron`: `LANE_EN` (F0B0; not on PCS_1/PCS_5, where F0B0 is set in every design),
  `LANE_USED` (F22B0), `MODESEL` (PCS10GE: F28B0; lanes 2/3/6/7, the only 10GE lanes); on PCS_0/PCS_4
  (per quad) `QUAD_USED` (F1B0+F4B0), `PWDN_N` (F27B0 when DISABLED), `IDDQ_PCS` (F21B0),
  `PHY_MODE` (SATAMODE: F25B0), `PIPE_LN2LK` (F5/F6/F7/F9/F14/F15/F19) and the word `BOND_MODE`
  (TX_BOND_MODE = RX_BOND_MODE, bit k sets F(38+k) and F(43+k)).
- The 9 static bits Radiant sets in every design (SERDES_REFCLK F0/F1/F2/F3/F10 B0, DOSCL_P18
  F6B1/F11B1, PCS_1/PCS_5 F0B0) are left undecoded: designs without them work on silicon.

Radiant writes the lane registers one byte at a time, omitting bytes that are at their default, in
descending order of (address bits 8-15, address); prjoxide's packer does the same (it writes the whole
block, including bytes at their default). Flags byte as for the other bus writes (0x10 vs 0xD0+CRC).

## Checks

- Packing the IP type from a build's attribute values reproduces every byte Radiant wrote for that
  lane: 7754 bytes over 112 attribute builds, the 10 single-lane protocol builds (1000BASE-X, 10GE on
  lane 2, CoaXPress, DP, eDP, G8B10B, JESD204B, QSGMII, SGMII, SLVS-EC) and all four lanes of XAUI.
- Decode -> pack of MPCS builds reproduces Radiant's frames and IP writes (order and data).
- LIFCL-40/17 and LFD2NX-40 packs are byte-identical; the LFCPNX regression set decodes unchanged.

## Method (scripts here; paths as used in the Radiant container, /work = ~/src/radiant-work)

1. Phase a, placement: `mkgen.py` (ipgen `-cfg` JSON; `-cfg_value` with more than one key is
   silently ignored) for LANE_ID 0-7 x NUM_LANES 1/2/4 (ipgen accepts x2 on 0/2/4/6, x4 on 0/4),
   `gen_top.py` (wrapper with every input from a register, refclk inputs left open: they only accept
   a DIFFCLKIO pad or a PLL), `build_one.sh`, `analyze.py`. Phase b: the 11 protocols the same way
   (10GE only on lanes 2/3/6/7; direction follows the protocol).
2. Base netlist: LSE's `synth.vm` of the default (1000BASE-X, lane 0) build, used as design source;
   only PCSX1 `defparam`s are edited per variant (the unedited netlist rebuilds identically).
3. Binary attributes: `mkpat.py` (11-bit pattern code, variants p/q) plus all-0/all-1 (z0/z1);
   TX/RX_BOND_MODE are held at baseline (synthesis requires them equal) and fuzzed separately;
   `solve_pat.py` (a byte Radiant does not write is at its default).
4. String attributes: legal values from map's own error messages (an invalid value gives
   "The valid ones are {...}"); two-valued ones pattern-coded (`mkpat_enum.py`, `solve_enum.py`),
   others one value per build (`solve_multi2.py`, against the packed baseline).
5. `write_db.py`, then `packtest.py` over all builds.
