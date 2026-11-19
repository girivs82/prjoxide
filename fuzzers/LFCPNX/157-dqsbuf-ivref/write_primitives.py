"""
Add DQSBUF_IVREF (DQSBUF plus the bank's IVREF_CORE) and OUTDELAYA to LFCPNX primitives.json, and the
DQSBUF parameters checked by this fuzzer's all-parameters builds. Re-running is a no-op.

Usage: write_primitives.py [database root]
"""
import copy
import json
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")
fn = os.path.join(root, "LFCPNX", "primitives.json")


def enum(default, values):
    return {"default": default, "values": values}


# checked on DQSBUF and DQSBUF_IVREF alike (allp_dqsbuf / allp_ivref: the same bits)
SHARED = {
    "FORCE_READ": enum("DISABLED", {"DISABLED": [], "ENABLED": ["FORCE_READ.ENABLED"]}),
    "FREE_WHEEL": enum("DDR", {"DDR": [], "GDDR": ["FREE_WHEEL.GDDR"]}),
    "MT_EN_READ": enum("DISABLED", {"DISABLED": [], "ENABLED": ["MT_EN_READ.ENABLED"]}),
    "MT_EN_WRITE": enum("DISABLED", {"DISABLED": [], "ENABLED": ["MT_EN_WRITE.ENABLED"]}),
    "MT_EN_WRITE_LEVELING": enum("DISABLED", {"DISABLED": [], "ENABLED": ["MT_EN_WRITE_LEVELING.ENABLED"]}),
    "RX_CENTERED": enum("ENABLED", {"ENABLED": [], "DISABLED": ["RX_CENTERED.DISABLED"]}),
    "SEL_READ_BIT_ENABLE_CYCLES": enum("NORMAL", {"NORMAL": [], "DELAYED_0P5_ECLK": ["SEL_READ_BIT_ENABLE_CYCLES.DELAYED_0P5_ECLK"]}),
    "BYPASS_WR_LEVEL_SMTH_LATCH": enum("SMOOTHING_PATH", {"SMOOTHING_PATH": [], "BYPASS_PATH": ["BYPASS_WR_LEVEL_SMTH_LATCH.BYPASS_PATH"]}),
    "BYPASS_WR_SMTH_LATCH": enum("SMOOTHING_PATH", {"SMOOTHING_PATH": [], "BYPASS_PATH": ["BYPASS_WR_SMTH_LATCH.BYPASS_PATH"]}),
    "BYPASS_READ_SMTH_LATCH": enum("SMOOTHING_PATH", {"SMOOTHING_PATH": [], "BYPASS_PATH": ["BYPASS_READ_SMTH_LATCH.BYPASS_PATH"]}),
}


def main():
    d = json.load(open(fn))
    p = d["primitives"]
    for k, v in SHARED.items():
        p["DQSBUF"]["parameters"].setdefault(k, v)
    if "DQSBUF_IVREF" not in p:
        e = copy.deepcopy(p["DQSBUF"])
        e["based_on"] = "DQSBUF"
        e["differences"] = (
            "DQSBUF plus the bank's VREF generator (IVREF_CORE): extra input bus IVREFI[6:0] (the LVSTL "
            "inputs' internal reference level, 0-127) and parameter LPDDR4_BL16_EN, which plain DQSBUF does "
            "not have (LSE: 'module DQSBUF does not have a parameter named LPDDR4_BL16_EN'). Every other "
            "parameter sets the same DQSBUF bits as on DQSBUF. Map places at most one per bank, and requires "
            "the group's DQS pad to be a differential LVSTL type (LVSTLD_I / LVSTLD_II). Using it sets "
            "BANK<n>.IVREF.ON in the bank reference tile, and Radiant gives the bank's LVSTL inputs "
            "VREF_LVSTL.VREF_INT. See fuzzers/LFCPNX/037-ivref and 157-dqsbuf-ivref.")
        e["parameters"]["LPDDR4_BL16_EN"] = enum("DISABLED", {"DISABLED": [], "ENABLED": ["LPDDR4_BL16_EN.ENABLED"]})
        e["bank_settings"] = ["BANK<n>.IVREF.ON"]
        for k in range(7):
            e["pins"]["IVREFI{}".format(k)] = {
                "pin": "IVREFI{}".format(k), "block": "IVREF_CORE",
                "note": "wire JIVREFI{}_IVREF_CORE of the bank reference tile (BANKREF3_DDR42 / "
                        "BANKREF4_DLY42_DDR41 / DDR40_ECLK_L), from CIBMUX C{} next to it; static level "
                        "or trained at runtime, no timing arcs characterised".format(k, k)}
        p["DQSBUF_IVREF"] = e
    if "OUTDELAYA" not in p:
        p["OUTDELAYA"] = {
            "site": "IOLOGIC",
            "pad": {"role": "output delay", "ports": ["DOUTI", "TOUTI", "DOUT", "TOUT"]},
            "note": ("Output / tristate delay line of an LPDDR4 DQ / DMI / DQS pad, between ODDRX4DQ(S) / TSHX4DQ(S) "
                     "and the pad: DOUTI / TOUTI from the gearing, DOUT / TOUT to the pad. Map accepts it only "
                     "after a memory DDR output, and only with both data and tristate through it. The training "
                     "pins (LOAD_N / MOVE / DIRECTION_LPDDR4_WT in, COUT_LPDDR4_WT out) are fabric pins whose "
                     "wires were not fuzzed yet."),
            "settings": ["OUTDELAYA.USED"],
            "parameters": {"MARGIN_TEST_ENABLE": enum("DISABLED", {"DISABLED": [], "ENABLED": ["OUTDELAYA.MARGIN_TEST_ENABLE.ENABLED"]})},
            "pins": {n: {"pin": n} for n in ("LOAD_N_LPDDR4_WT", "DIRECTION_LPDDR4_WT", "MOVE_LPDDR4_WT", "COUT_LPDDR4_WT")},
        }
    d["_comment"] = d["_comment"].replace("fuzzers 070, 151-156.", "fuzzers 070, 151-157.")
    json.dump(d, open(fn, "w"), indent=1)
    open(fn, "a").write("\n")
    print("ok")


if __name__ == "__main__":
    main()
