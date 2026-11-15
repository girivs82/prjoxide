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
  - `VREF_LVSTL`: OFF or VREF_INT, the internal input reference (`VREF=VREF_INT`), which
    Radiant's flow sets on every LVSTL_I input and bidir (pad report "VREF:VREF_INT"). VREF_INT is
    PIOA F17B1+F74B0+F78B0 (first tile) and PIOB F74B0+F82B0+F86B0 (second tile), the same for
    inputs and bidirs. VREF1_LOAD and VREF2_LOAD (and leaving VREF unset in the structural flow)
    give the same pad bits as OFF; they only set F94B1 in the tile of the bank's VREF1 or VREF2 pin
    (SYSIO_B<n>_1_V18 for VREF1; _V18_32 / _V18_42 / _V18_51 for VREF2), which 032's `VREF` enum
    of that tile decodes. VREF_INT on HSUL12 and SSTL15_I is accepted but sets no bits.
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
alone gives misleading output, so three post-passes run on LFCPNX decodes. Neither changes which bits
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
| SSTL135_I/II (and D) | 1V35 (SSTL135_II only) | 1V35 | SLEWRATE_REF |
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

(c) **Single-ended LVSTL with the internal reference.** An LVSTL_I / LVSTL_II pad with
`VREF=VREF_INT` sets SEIO18 BASE_TYPE `*_LVSTL_*` and `VREF_LVSTL.VREF_INT`. Together these cover
every set bit of DIFFIO18 BASE_TYPE `*_LVSTLD_*` (the differential option's F13B1 is a clear bit),
so the pad also decoded as LVSTLD_I. A differential LVSTL pair never sets VREF_INT. So when PIOA
decodes `VREF_LVSTL.VREF_INT` with a single-ended LVSTL BASE_TYPE, the DIFFIO18 `*_LVSTLD_*` line
is dropped if the remaining features explain its bits.
- Effect, e.g. on 037-ivref's DQSBUF_IVREF designs: the single-ended DQ pads lose the extra LVSTLD_I
  line.
- The differential DQS pads keep theirs.
- The FASM packs to the same bitstream.

## SSTL15_II / SSTL135_II drive

Radiant accepts one DRIVE for SSTL15_II and SSTL135_II outputs: 10. For any other value map says
"change DRIVE to 10". Its synthesized flow sets it by default. The structural builds of this
fuzzer and 032 set BASE_TYPE OUTPUT_SSTL15_II with the drive code left at 0, so in Radiant-built
designs the code was unknown:
- PIOA: F12B1 + F13B1;
- PIOB: F90B0.

`gen_class2.py` builds one output of the IO type on a pad of every one of the 33 bank 3 / 4 / 5 SYSIO
tile types (PB<n>A for the first-tile types, PB<n>B for the second-tile ones). For SSTL15_II and
SSTL135_II alike, every tile type gives the same code:

| PIO | drive code bits | DRIVE=10 |
|---|---|---|
| PIOA (first tile) | F9B1-F13B1 | F12B1, F13B1 set; F9B1-F11B1 clear |
| PIOB (second tile) | F89B0-F93B0 | F89B0, F90B0 set; F91B0-F93B0 clear |

F89B0 is also set when PIOB is unused, so only F90B0 showed as unknown. Both being set was read by
decoding with each candidate option. It matches PIOA by the correspondence of the existing 2 / 4 / 8
options (F13B1 - F89B0, F12B1 - F90B0, F10B1 - F92B0, F9B1 / F11B1 - F91B0 / F93B0).

`write_class2_drive.py` adds option `10` to DRIVE_1V5, and a DRIVE_1V35 enum with the same option,
on all 33 tile types. An SSTL135_II output decodes as SSTL15_II (identical bits; see the canonical
options above), so its drive decodes as DRIVE_1V5 10. DRIVE_1V35 is there for writing FASM for
SSTL135_II. SSTL15_I / SSTL135_I have no DRIVE; their code is part of their BASE_TYPE.

## Run

    fuzzer.py            # bank, the 44 pads (about 1300 Radiant builds), then VREF_LVSTL (44)
    describe.py          # descriptions (bits untouched)
    gen_class2.py <pin list> SSTL15_II <name>   # class-II output design, built with radiant.sh
    write_class2_drive.py                       # DRIVE_1V5 / DRIVE_1V35 10

`probe.py` to `probe6.py` are the exploratory builds the above is based
on (one pad pair, value discovery, bank-level tiles, VREF on LVSTL_I / HSUL12 / SSTL15_I).
