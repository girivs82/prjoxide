"""
SYSCONFIG settings on LFCPNX-100: LIFCL's 090-sysconfig enums (ldc_set_sysconfig in the synthesized
flow), on LFCPNX-100's configuration-row tiles (the same tile types as LIFCL-40, at its own columns).

Usage: fuzzer.py
"""
import importlib.util
import os

from fuzzconfig import FuzzConfig
import nonrouting

_spec = importlib.util.spec_from_file_location(
    "iol070", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "070-iologic_mode", "fuzzer.py"))
_spec.loader.exec_module(importlib.util.module_from_spec(_spec))   # robust enum wrapper, work-dir cleanup

cfg = FuzzConfig(job="SYSCONFIG100", device="LFCPNX-100", sv="../shared/empty_100.v",
                 tiles=["CIB_R0C135:EFB_0", "CIB_R0C132:BANKREF0", "CIB_R0C137:EFB_1_OSC", "CIB_R0C139:EFB_2",
                        "CIB_R0C141:I2C_EFB_3", "CIB_R0C145:PMU", "CIB_R0C159:MIB_CNR_32_FAFD",
                        "CIB_R0C157:IREF_P33", "CIB_R2C159:POR"])

SETTINGS = [
    ("MASTER_SPI_PORT", ["DISABLE", "SERIAL", "DUAL", "QUAD"], "status of master SPI port after configuration"),
    ("SLAVE_SPI_PORT", ["DISABLE", "SERIAL", "DUAL", "QUAD"], "status of slave SPI port after configuration"),
    ("SLAVE_I2C_PORT", ["DISABLE", "ENABLE"], "status of slave I2C port after configuration"),
    ("SLAVE_I3C_PORT", ["DISABLE", "ENABLE"], "status of slave I3C port after configuration"),
    ("JTAG_PORT", ["DISABLE", "ENABLE"], "status of JTAG port after configuration"),
    ("DONE_PORT", ["DISABLE", "ENABLE"], "use DONE output after configuration"),
    ("INITN_PORT", ["DISABLE", "ENABLE"], "use INITN input after configuration"),
    ("PROGRAMN_PORT", ["DISABLE", "ENABLE"], "use PROGRAMN input after configuration"),
]


def main():
    cfg.setup()
    empty = cfg.build_design(cfg.sv, {})
    cfg.sv = "empty_presyn_100.v"
    cfg.struct_mode = False
    for name, values, desc in SETTINGS:
        nonrouting.fuzz_enum_setting(cfg, empty, "SYSCONFIG." + name, values,
                                     lambda x, n=name: dict(sysconfig="{}={}".format(n, x)), False,
                                     assume_zero_base=True, desc=desc)


if __name__ == "__main__":
    main()
