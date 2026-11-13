"""
DLLDEL settings (the primary clock input delays) of LFCPNX's PCLK_DLY tile types: LIFCL's
155-dlldel settings on the four LFCPNX-100 DLLDEL sites (the pips are 002c-clock-tile-pips').

Usage: fuzzer.py [tile type ...]
"""
import sys

from fuzzconfig import FuzzConfig
import fuzzloops
import nonrouting

# tile type: (tile, DLLDEL site R/C)
SITES = {
    "PCLK_DLY_10": ("CIB_R36C159:PCLK_DLY_10", (36, 158)),
    "PCLK_DLY_20": ("CIB_R39C159:PCLK_DLY_20", (39, 158)),
    "PCLK_DLY_60": ("CIB_R39C0:PCLK_DLY_60", (39, 1)),
    "PCLK_DLY_70": ("CIB_R36C0:PCLK_DLY_70", (36, 1)),
}
# setting names as LIFCL's (DLLDEL10 for PCLK_DLY_10, ...)


def main():
    sel = [tt for tt in SITES if not sys.argv[1:] or tt in sys.argv[1:]]

    def per_tt(tt):
        tile, (r, c) = SITES[tt]
        cfg = FuzzConfig(job="DLL" + tt[-2:], device="LFCPNX-100", sv="../shared/empty_100.v", tiles=[tile])
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "dlldel_100.v"
        site = "DLLDEL_CORE_R{}C{}".format(r, c)
        dd = tt[-2:]

        def get_substs(mode="DLLDEL_CORE", kv=None, mux=False):
            if kv is None:
                config = ""
            elif mux:
                val = "#SIG"
                if kv[1] in ("0", "1"):
                    val = kv[1]
                if kv[1] == "INV":
                    val = "#INV"
                config = "{}::::{}={}".format(mode, kv[0], val)
            else:
                config = "{}:::{}={}".format(mode, kv[0], kv[1])
            return dict(mode=mode, cmt="//" if mode == "NONE" else "", config=config, site=site)

        def intval(vec):
            x = 0
            for i, b in enumerate(vec):
                if b:
                    x |= (1 << i)
            return x

        nonrouting.fuzz_enum_setting(cfg, empty, "DLLDEL{}.MODE".format(dd), ["NONE", "DLLDEL_CORE"],
                                     lambda x: get_substs(mode=x), False, desc="DLLDEL primitive mode")
        nonrouting.fuzz_enum_setting(cfg, empty, "DLLDEL{}.ENABLE".format(dd), ["ENABLED", "DISABLED"],
                                     lambda x: get_substs(kv=("ENABLE", x)), False, desc="DLLDEL primitive mode")
        nonrouting.fuzz_enum_setting(cfg, empty, "DLLDEL{}.DEL_ADJUST".format(dd), ["PLUS", "MINUS"],
                                     lambda x: get_substs(kv=("DEL_ADJUST", x)), False)
        nonrouting.fuzz_word_setting(cfg, "DLLDEL{}.ADJUST".format(dd), 9,
                                     lambda x: get_substs(kv=("ADJUST", str(intval(x)))))
        nonrouting.fuzz_enum_setting(cfg, empty, "DLLDEL{}.CLKINMUX".format(dd), ["CLKIN", "INV"],
                                     lambda x: get_substs(kv=("CLKIN", x), mux=True), False)

    fuzzloops.parallel_foreach(sel, per_tt)


if __name__ == "__main__":
    main()
