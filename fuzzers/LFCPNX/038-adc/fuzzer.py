"""
ADC (ADC_CORE, tile CIB_R68C159:ADC) configuration on LFCPNX-100.

Radiant places an ADC only at performance grade 8 or 9 in the industrial operating condition, so
these builds use the synthesized flow (LSE) with SPEED_GRADE=9_High-Performance_1.0V and
OPER_COND=industrial (postsyn -oc). Each parameter is fuzzed against the design with all
parameters unset (Radiant's defaults); legal values are the ones map lists in its errors.

Usage: fuzzer.py
"""
import os

from fuzzconfig import FuzzConfig
import fuzzloops
import nonrouting

os.environ.setdefault("SPEED_GRADE", "9_High-Performance_1.0V")
os.environ.setdefault("OPER_COND", "industrial")

EN = ["ENABLED", "DISABLED"]
PARAMS = [("ADC_ENP", EN), ("CTLCOMPSW1", EN), ("CTLCOMPSW2", EN), ("CTLCOMPSW3", EN),
          ("DF", ["STRAIGHT_BINARY", "TWOS_COMPLEMENT"]), ("EN_COMP1", EN), ("EN_COMP2", EN),
          ("EN_COMP3", EN), ("OMA", ["BIPOLAR", "UNIPOLAR"]), ("OMB", ["BIPOLAR", "UNIPOLAR"]),
          ("REFBUFAEN", EN), ("REFBUFBEN", EN), ("SLEEP", EN),
          ("VREFACFG", ["1P0_TO_1P2", "1P2_TO_1P4", "1P4_TO_1P6", "1P6_TO_1P8"]),
          ("VREFBCFG", ["1P0_TO_1P2", "1P2_TO_1P4", "1P4_TO_1P6", "1P6_TO_1P8"]),
          ("VREFASEL", ["INTERNAL", "EXTERNAL"]), ("VREFBSEL", ["INTERNAL", "EXTERNAL"])]


def make_cfg(job):
    cfg = FuzzConfig(job=job, device="LFCPNX-100", sv="adc_100.v", tiles=["CIB_R68C159:ADC"])
    cfg.struct_mode = False
    return cfg


def main():
    base = make_cfg("ADCBASE")
    base.setup(skip_specimen=True)
    empty = base.build_design(base.sv, dict(cmt="//", params=""), "empty_")
    adc = base.build_design(base.sv, dict(cmt="", params=""), "adc_")
    nonrouting.fuzz_enum_setting(base, empty, "ADC.MODE", ["NONE", "ADC_CORE"],
                                 lambda x: dict(cmt="//" if x == "NONE" else "", params=""), False,
                                 desc="ADC_CORE used")

    def per_param(p):
        name, vals = p
        cfg = make_cfg("ADC_" + name)
        cfg.setup(skip_specimen=True)
        nonrouting.fuzz_enum_setting(cfg, adc, "ADC." + name, vals,
                                     lambda x: dict(cmt="", params='.{}("{}")'.format(name, x)), False)

    def per_word(_):
        cfg = make_cfg("ADC_CLK_DIV")
        cfg.setup(skip_specimen=True)
        nonrouting.fuzz_word_setting(cfg, "ADC.CLK_DIV", 8,
            lambda v: dict(cmt="", params='.CLK_DIV("{}")'.format(sum(1 << i for i, b in enumerate(v) if b))))

    fuzzloops.parallel_foreach(PARAMS + [("CLK_DIV", None)],
                               lambda p: per_word(p) if p[0] == "CLK_DIV" else per_param(p))


if __name__ == "__main__":
    main()
