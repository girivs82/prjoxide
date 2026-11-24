# 090-sysconfig: SYSCONFIG settings (LFCPNX-100)

LIFCL's 090-sysconfig enums, set with `ldc_set_sysconfig {...}` in the synthesized flow
(`empty_presyn_100.v`), diffed over LFCPNX-100's configuration-row tiles: EFB_0 .. PMU, BANKREF0,
IREF_P33, MIB_CNR_32_FAFD, POR.

| Setting | LFCPNX-100 | vs LIFCL-40 |
|---|---|---|
| MASTER_SPI_PORT | EFB_1_OSC F20B0 (SERIAL, DUAL), + F25B0 (QUAD) | same |
| SLAVE_SPI_PORT | EFB_1_OSC F21B0, + F26B0 (QUAD) | same |
| SLAVE_I2C_PORT | EFB_1_OSC F29B0 | same |
| SLAVE_I3C_PORT | EFB_0 F49B0 | same |
| JTAG_PORT | PMU F38B0 (see below) | LIFCL has no bit for it |
| DONE_PORT, INITN_PORT, PROGRAMN_PORT | no bits | same |

## JTAG_PORT: DISABLE locks JTAG out

F38B0 is set by every design, the empty one included: JTAG is enabled by default. It is an always_on
bit of PMU, so the packer sets it in every bitstream.

The fuzzer (assume_zero_base) leaves DISABLE with no bits, and then DISABLE could not clear it.
`fix_jtag_port.py` writes DISABLE as F38B0 cleared. The packer applies always_on bits before the
FASM, so a FASM line `SYSCONFIG.JTAG_PORT.DISABLE` does clear it.

**WARNING:** a bitstream with JTAG_PORT DISABLE has no JTAG after configuration. Nothing sets it by
default: FASM without a JTAG_PORT line keeps JTAG enabled. A tool writing FASM (SKALP) must never
emit DISABLE unless locking out JTAG is intended. The enum's database description says the same.

## Run

    fuzzer.py
    fix_jtag_port.py
