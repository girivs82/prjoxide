"""
CHIP.SPEED on LFCPNX-100: LIFCL's 040-speed (the same empty design built for the High-Performance and
the Low-Power 1.0 V speed grade, diffed over every tile).

Usage: fuzzer.py
"""
import importlib.util
import os

from fuzzconfig import FuzzConfig
import database
import nonrouting

_spec = importlib.util.spec_from_file_location(
    "iol070", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "070-iologic_mode", "fuzzer.py"))
_spec.loader.exec_module(importlib.util.module_from_spec(_spec))   # robust enum wrapper, work-dir cleanup

speed_map = {
    "FAST_1V0": "7_High-Performance_1.0V",
    "SLOW_1V0": "7_Low-Power_1.0V",
}

all_tiles = set(database.get_tilegrid("LFCPNX", "LFCPNX-100")["tiles"].keys())
cfg = FuzzConfig(job="SPEED", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=all_tiles)


def main():
    cfg.setup()
    empty = cfg.build_design(cfg.sv, {})
    cfg.sv = "speed_100.v"
    nonrouting.fuzz_enum_setting(cfg, empty, "CHIP.SPEED", ["SLOW_1V0", "FAST_1V0"],
                                 lambda x: {"speed": speed_map[x]}, True,
                                 desc="Adjust back bias for high speed or low power")


if __name__ == "__main__":
    main()
