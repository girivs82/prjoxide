"""
Configuration cores on LFCPNX-100, through their documented user primitives in the synthesized flow
(see README.md):
- MULTIBOOT -> CONFIG_MULTIBOOT_CORE: SOURCESEL, MSPIADDR;
- CONFIG_CLKRST_CORE: the GSR disables MC*GSRNDIS.
The settings tables are LIFCL's 131-config-ip.

LIFCL's fuzzer places structural instances at TCONFIG_<core><n> sites; on LFCPNX-100 those names are
not known without lapie, and an unplaced structural instance is dropped (it sets no bits). In the
synthesized flow map places the cores itself. LFCPNX-100 has no CONFIG_HSE_CORE or CONFIG_LMMI_CORE
(sv2udb: unknown module; LSE knows no CONFIG_LMMI / CONFIG_LMMIC), and CONFIG_IP_CORE /
CONFIG_WDT_CORE have no documented user primitive, so they are not fuzzed.

Usage: fuzzer.py
"""
import importlib.util
import os

from fuzzconfig import FuzzConfig
import nonrouting

_spec = importlib.util.spec_from_file_location(
    "iol070", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "070-iologic_mode", "fuzzer.py"))
_spec.loader.exec_module(importlib.util.module_from_spec(_spec))   # robust enum wrapper, work-dir cleanup

TILES = ["CIB_R0C135:EFB_0", "CIB_R0C137:EFB_1_OSC", "CIB_R0C139:EFB_2", "CIB_R0C141:I2C_EFB_3", "CIB_R0C145:PMU"]

# (primitive, core name in the database, instance template with {params})
CORES = [
    ("MULTIBOOT", "CONFIG_MULTIBOOT_CORE",
     "MULTIBOOT #({params}) mb_i (.AUTOREBOOT(s[33]), .MSPIMADDR(s[31:0]));"),
    ("CONFIG_CLKRST_CORE", "CONFIG_CLKRST_CORE",
     "CONFIG_CLKRST_CORE #({params}) clkrst_i (.LMMI_CLK(clk), .LMMI_LRST_N(s[32]), .LMMI_CLK_O(), .LMMI_RST());"),
]
SETTINGS = {
    "CONFIG_MULTIBOOT_CORE": [("SOURCESEL", ["DIS", "EN"], "selects next address from input pins or fixed parameter")],
    "CONFIG_CLKRST_CORE": [
        ("MCJTAGGSRNDIS", ["DIS", "EN"], ""),
        ("MCLMMIGSRNDIS", ["DIS", "EN"], ""),
        ("MCSEDCGSRNDIS", ["DIS", "EN"], ""),
        ("MCWDTGSRNDIS", ["DIS", "EN"], ""),
    ],
}
WORDS = {"CONFIG_MULTIBOOT_CORE": [("MSPIADDR", 32, "SPI flash fixed next address")]}


def main():
    cfg = FuzzConfig(job="CONFIGIP", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=TILES)
    cfg.setup()
    cfg.sv = "ip_100.v"
    cfg.struct_mode = False
    for prim, core, inst in CORES:
        def substs(params=None, inst=inst):
            if params is None:
                return dict(cmt="//", body=inst.format(params=""))
            p = ", ".join('.{}("{}")'.format(k, v) for k, v in params)
            return dict(cmt="", body=inst.format(params=p))
        # the reference: the core with no parameter set
        base = cfg.build_design(cfg.sv, substs([]), "base_{}_".format(core))
        for name, values, desc in SETTINGS[core]:
            nonrouting.fuzz_enum_setting(cfg, base, "{}.{}".format(core, name), values,
                                         lambda x, n=name: substs([(n, x)]), False, desc=desc)
        for name, width, desc in WORDS.get(core, []):
            nonrouting.fuzz_word_setting(cfg, "{}.{}".format(core, name), width,
                lambda x, n=name: substs([(n, "0b" + "".join(reversed(["1" if b else "0" for b in x])))]),
                desc=desc)


if __name__ == "__main__":
    main()
