"""
The internal oscillator (OSC_CORE) on LFCPNX-100: LIFCL's 091-osc settings, at site OSC_CORE_R1C137
in tile CIB_R0C137:EFB_1_OSC (the site Radiant placed the oscillator at in 038-adc's designs).

Configuration only. LIFCL's 091 also fuzzes the oscillator's routing with lapie, which is not used
here; the fabric connections come from Radiant-routed designs (see README.md).

Usage: fuzzer.py
"""
import importlib.util
import os

from fuzzconfig import FuzzConfig
import nonrouting

_spec = importlib.util.spec_from_file_location(
    "iol070", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "070-iologic_mode", "fuzzer.py"))
_spec.loader.exec_module(importlib.util.module_from_spec(_spec))   # robust enum wrapper, work-dir cleanup

cfg = FuzzConfig(job="OSCMODE100", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R0C137:EFB_1_OSC"])


def main():
    cfg.setup()
    empty = cfg.build_design(cfg.sv, {})
    cfg.sv = "osc_100.v"

    def bin_to_int(x):
        return sum(1 << i for i, b in enumerate(x) if b)

    def get_substs(mode="NONE", kv=None):
        config = "" if kv is None else "{}:::{}={}".format(mode, kv[0], kv[1])
        return dict(mode=mode, cmt="//" if mode == "NONE" else "", config=config)

    E = nonrouting.fuzz_enum_setting
    E(cfg, empty, "OSC_CORE.MODE", ["NONE", "OSC_CORE"], lambda x: get_substs(mode=x), False,
      desc="OSC_CORE primitive mode")
    nonrouting.fuzz_word_setting(cfg, "OSC_CORE.HF_CLK_DIV", 8,
        lambda x: get_substs(mode="OSC_CORE", kv=("HF_CLK_DIV", str(bin_to_int(x)))),
        desc="high frequency oscillator output divider")
    nonrouting.fuzz_word_setting(cfg, "OSC_CORE.HF_SED_SEC_DIV", 8,
        lambda x: get_substs(mode="OSC_CORE", kv=("HF_SED_SEC_DIV", str(bin_to_int(x)))),
        desc="high frequency oscillator SED secondary output divider")
    for name, desc in [("DTR_EN", ""),
                       ("HF_FABRIC_EN", "enable HF oscillator trimming from input pins"),
                       ("HF_OSC_EN", "enable HF oscillator"),
                       ("HFDIV_FABRIC_EN", "enable HF divider from parameter"),
                       ("LF_FABRIC_EN", "enable LF oscillator trimming from input pins"),
                       ("LF_OUTPUT_EN", "enable LF oscillator output"),
                       ("DEBUG_N", "enable debug mode")]:
        E(cfg, empty, "OSC_CORE." + name, ["ENABLED", "DISABLED"],
          lambda x, n=name: get_substs(mode="OSC_CORE", kv=(n, x)), False, desc=desc)


if __name__ == "__main__":
    main()
