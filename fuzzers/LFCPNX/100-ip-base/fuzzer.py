"""
Find IP-bus base addresses for LFCPNX-100 hard IP (PLL, EBR WID, LRAM, PMU, I2CFIFO, PCIe, ...).

Inputs only: each candidate site gets one primitive with one non-default IP
setting; we read back which IP address the bitstream writes. Site names on
LFCPNX are not all known, so each region lists candidates (derived from the
LIFCL site<->tile offsets) and the first one Radiant accepts wins. Rejected
candidates are logged to work/IPADDR100/sites.log for the next iteration.

Writes database/LFCPNX/LFCPNX-100/baseaddr.json (merged with what is there).
"""
import fuzzconfig
import database
from os import path
import os
import libpyprjoxide
import json

cfg = fuzzconfig.FuzzConfig(job="IPADDR100", device="LFCPNX-100", sv="ip.v", tiles=[])

# (region name in baseaddr.json, primitive setting key, candidate sites)
regions = [
    ("PLL_ULC", "PLL_CORE", ["PLL_ULC"]),
    ("PLL_URC", "PLL_CORE", ["PLL_URC"]),
    ("PLL_LLC", "PLL_CORE", ["PLL_LLC"]),
    ("PLL_LRC", "PLL_CORE", ["PLL_LRC"]),
    # EBR_1 tile CIB_R11C100 -> site at (-1,-1) as on LIFCL; only the WID matters
    ("EBR_WID0", "EBR_CORE_WID0", ["EBR_CORE_R10C99", "EBR_CORE_R10C3", "EBR_CORE_R10C2"]),
    ("EBR_WID1", "EBR_CORE_WID1", ["EBR_CORE_R10C99", "EBR_CORE_R10C3", "EBR_CORE_R10C2"]),
    ("EBR_WID2047", "EBR_CORE_WID2047", ["EBR_CORE_R10C99", "EBR_CORE_R10C3", "EBR_CORE_R10C2"]),
    # PMU / I2CFIFO: LIFCL site is one row below the CIB tile
    ("PMU_CORE_R1C145", "PMU_CORE", ["PMU_CORE_R1C145", "PMU_CORE_R0C145", "PMU_CORE"]),
    ("I2CFIFO_CORE_R1C141", "I2CFIFO_CORE", ["I2CFIFO_CORE_R1C141", "I2CFIFO_CORE_R0C141", "I2CFIFO_CORE"]),
    # LRAM: LRAM_0..2 on the right edge, LRAM_3..6 on the top edge. Offsets are guesses.
    ("LRAM_CORE_R16C158", "LRAM_CORE", ["LRAM_CORE_R16C158", "LRAM_CORE_R20C158", "LRAM_CORE_R21C158"]),
    ("TPCIE_CORE20", "PCIE_CORE", ["TPCIE_CORE20", "PCIE_CORE_R1C20", "PCIE_CORE"]),
]

ip_settings = {
    "EBR_CORE_WID0": "EBR_CORE:::WID=0b00000000000",
    "EBR_CORE_WID1": "EBR_CORE:::WID=0b00000000001",
    "EBR_CORE_WID2047": "EBR_CORE:::WID=0b11111111111",
    "PLL_CORE": "PLL_CORE:::DIVA=1",
    "PMU_CORE": "PMU_CORE:::WKCOUNT0=0b00000001",
    "I2CFIFO_CORE": "I2CFIFO_CORE:::I2CSLVADDRA=0b0000000001",
    "PCIE_CORE": "PCIE_CORE:::PHY_MODE=0b0001",
    "LRAM_CORE": "LRAM_CORE:::CFG_INIT_ID=0b00000000000",
}

ip_abits = {
    "PLL_CORE": 7, "PMU_CORE": 4, "I2CFIFO_CORE": 6,
    "PCIE_CORE": 17, "EBR_CORE": 17, "LRAM_CORE": 17,
}

def main():
    cfg.setup(skip_specimen=True)
    out = path.join(database.get_db_root(), "LFCPNX", cfg.device, "baseaddr.json")
    with open(out) as jf:
        ip_base = json.load(jf).get("regions", {})
    log = open(path.join(cfg.workdir, "sites.log"), "a")
    for region, prim, sites in regions:
        prim_type = prim.split("_WID")[0]
        for i, site in enumerate(sites):
            bit = cfg.build_design(cfg.sv, dict(cmt="", prim=prim_type, site=site, config=ip_settings[prim]),
                                   prefix="{}_{}_".format(region, i))
            if not path.exists(bit):
                print("REJECTED {} site {}".format(region, site), file=log, flush=True)
                continue
            chip = libpyprjoxide.Chip.from_bitstream(fuzzconfig.db, bit)
            ipv = chip.get_ip_values()
            if len(ipv) == 0:
                print("NO-IP-WRITE {} site {}".format(region, site), file=log, flush=True)
                continue
            addr = ipv[0][0]
            ip_base[region] = {"addr": addr & ~((1 << ip_abits[prim_type]) - 1), "abits": ip_abits[prim_type]}
            print("OK {} site {} addr 0x{:08x}".format(region, site, ip_base[region]["addr"]), file=log, flush=True)
            print("{}: 0x{:08x} (site {})".format(region, ip_base[region]["addr"], site))
            break
        else:
            print("!! no accepted site for {}".format(region))
    with open(out, "w") as jf:
        print(json.dumps(dict(regions=ip_base), sort_keys=True, indent=4), file=jf)

if __name__ == "__main__":
    main()
