# 036-hsio-vref: LVSTL, referenced-standard slew rate, and HP-IO decode choices (LFCPNX-100)

Adds to 032-hsio_mode's HP-bank (banks 3, 4, 5) IO database, with the same structural builds
(`../032-hsio_mode/iob_100.v`, Radiant 2026.1, `STRUCT_VER=1`, readback images) on 032's 44 pads.
Only new options and new enums are written; the database refuses an option that would change an
existing one, so FASM that packed before packs to the same bitstream.

## What the builds show

- **Input class / VREF.** On SSTL, HSTL and HSUL inputs, the only bits beyond the plain input are the
  existing `VREF` enum (VREF1_LOAD = F81+F82+F86 on PIOB). An input sets no class bits of its own.
- **Slew rate.** The MED setting is encoded differently for the referenced standards (SSTL, HSTL,
  HSUL, LVSTL) than for LVCMOS*H: PIOA F90+F91 (LVCMOS: F90), PIOB F6B1+F7B1 (LVCMOS: F7B1). SLOW
  and FAST are the same for both. Radiant's flow sets MED on these outputs, which is why HSUL12 and
  SSTL outputs decoded with unknown F90/F91 or F6B1/F7B1 bits before. New enum `SLEWRATE_REF`.
- **LVSTL_I** (`IO_TYPE=LVSTL_I`, `BANK_VCCIO=1.1`; Radiant rejects the `LVSTL11*` names):
  - BASE_TYPE: new INPUT/OUTPUT/BIDIR options (default drive 8 included, as 032 does for the
    other types);
  - `DRIVE_LVSTL`: 2, 4, 6, 8 (default), 10, 12 (16 and up are refused); 12 sets none of the code
    bits, so an LVSTL_I output at drive 12 has the same PIO bits as an LVSTL_II output;
  - `TERMINATION_1V1`: OFF (= Radiant's default), 40, 48, 60, 80, 120 ohm, on inputs and bidirs.
    Radiant also accepts 50, 75 and 150, which set no termination bits and clear the F95 bit that
    OFF sets. Those three are recorded as options too; they have no set bits, so they never decode;
  - VREF: an LVSTL input has no VREF bits at the pad (VREF1_LOAD, the default, VREF2_LOAD and OFF
    give the same pad bits). The choice only shows as F94B1 in the tile of the bank's VREF1 or
    VREF2 pin (SYSIO_B<n>_1_V18 for VREF1; _V18_32 / _V18_42 / _V18_51 for VREF2), which 032's
    `VREF` enum of that tile already decodes. No LVSTL VREF enum is written.
- **LVSTL_II**: BASE_TYPE options; DRIVE and TERMINATION are accepted but have no effect.
- **LVSTLD_I / LVSTLD_II** (differential, on PIOA's DIFFIO18): BASE_TYPE options. The drive and
  termination of LVSTLD_I are those of LVSTL_I.
- **Bank / chip level at VCCIO 1.1 V.** VccIO itself has no bits in the HP banks' BANKREF tiles (035
  found none for 1.0 to 1.8 V either). LVSTL sets:
  - `BANK<n>.LVSTL` in the bank's BANKREF tile: bank 3 LVSTL_I = F1B1+F13B1+F14B1, LVSTL_II =
    F1B1+F14B1+F15B1; banks 4 and 5 LVSTL_I = F17B0+F18B0+F30B0, LVSTL_II = F16B0+F17B0+F30B0,
    in addition to `BANK<n>.REF_IO.ON`;
  - `LVSTL` in DOSCL_P18 (R68C0), the same for every HP bank: LVSTL_I = F2B2+F5B2,
    LVSTL_II adds F3B2.

## Decode choices (lfcpnx_decode.rs, LFCPNX only)

The tile decoder picks, per enum, the longest option whose bits all match. On these tiles that
alone gives misleading output, so two post-passes run on LFCPNX decodes. Neither changes which bits
are explained (a feature is only relabelled to another matching option, or dropped when the
remaining features explain all of its set bits), so packing the decoded FASM gives the same
bitstream.

(a) **Pair context.** A pad pair's PIOA has enums in both tiles (`SYSIO_B<n>_0*` and
`SYSIO_B<n>_1*`). In the second tile, PIOA's BASE_TYPE only sees F89B0, which is PIOB's unused
state (its default drive code), so on its own it decoded as OUTPUT_SSTL15_II. These second-tile PIOA
enums now take the option the first tile decodes for PIOA. When PIOA is unused, that is the existing
`NONE` option, which on every second-tile type is exactly that unused pattern (F89B0), so no new
option was needed. When the first tile's option has no second-tile bits (HSUL12), the line is
dropped if PIOB's features explain the bits.

(b) **Shared encodings.** `DRIVE_<v>`, `TERMINATION_<v>`, `SLEWRATE` / `SLEWRATE_REF` share bits, so several decoded at once (e.g. DRIVE_1V2.8, DRIVE_1V5.8, DRIVE_1V8.8 and
DRIVE_HSUL12.8 for one output). Only the ones for the PIO's IO type (from its BASE_TYPE,
differential first) are kept:

| IO type | DRIVE_ | TERMINATION_ | slew |
|---|---|---|---|
| LVCMOS18H, LVCMOS10R | 1V8 | 1V8 | SLEWRATE |
| LVCMOS15H | 1V5 | 1V5 | SLEWRATE |
| LVCMOS12H | 1V2 | 1V2 | SLEWRATE |
| LVCMOS10H | 1V0 | 1V0 | SLEWRATE |
| SSTL15_I/II, HSTL15_I (and D) | 1V5 | 1V5 | SLEWRATE_REF |
| SSTL135_I/II (and D) | none | 1V35 | SLEWRATE_REF |
| HSUL12 (and D) | HSUL12 | 1V2 | SLEWRATE_REF |
| LVSTL_I, LVSTL_II (and D) | LVSTL | 1V1 | SLEWRATE_REF |

**Canonical options.** Some options of one enum have identical bits, so the bitstream cannot tell
them apart (e.g. on PIOB: BIDIR_HSUL12, BIDIR_HSTL15_I, BIDIR_LVCMOS15H and BIDIR_LVCMOS18H;
BIDIR_SSTL15_I and BIDIR_SSTL135_I; INPUT_LVSTL_I and INPUT_LVSTL_II). The decoder emits the last
of each group by name. Any member packs to the same bits. Across enums, OUTPUT_LVSTL_II has the PIO
bits of OUTPUT_LVSTL_I with DRIVE_LVSTL 12, so such an output decodes as OUTPUT_LVSTL_II; the bank's
`BANK<n>.LVSTL` tells the two classes apart. The groups differ by tile
type; `describe.py` writes each enum's groups into its database description, as
`canonical = equivalent = ...`.

## Run

    fuzzer.py            # bank, then the 44 pads (about 1300 Radiant builds)
    describe.py          # descriptions (bits untouched)

`probe.py`, `probe2.py`, `probe3.py` and `probe4.py` are the exploratory builds the above is based
on (one pad pair, value discovery, bank-level tiles).
