"""
Fuzz the pips of clock tile types that LFCPNX's database lacks entirely, using LIFCL's
tiles of the same name as the candidate list (no lapie).

For each tile type, every (from, to) pip in LIFCL/tiletypes/<type>.ron is translated to
Lattice absolute wire names at the LFCPNX-100 instance (prjoxide's normalize_wire is the
oracle) and forced in a separate design with fuzz_pip_list; arcs Radiant rejects are
reported as ABSENT. Arcs that change no bits and are zero-bit mux options in LIFCL are
stored as empty-bit pips, as LIFCL does.

Global wires (prjoxide's G:<name>) carry no location in their normalised name, so the R/C
Radiant uses for each global bel was found by forcing one of its arcs at every R/C in a small
window around the tile with single sv2udb builds (Radiant exits with a fatal error for wire
names that do not exist). Exactly one R/C was accepted per bel; see GLOBAL_LOCS and --locate.

Usage: python3 fuzzer.py [tile type ...]   (default: all below)
       python3 fuzzer.py --locate [tile type ...]   re-run the global bel location scan
"""
import os
import re
import subprocess
import sys

import database
import libpyprjoxide
from fuzzconfig import FuzzConfig
from interconnect import fuzz_pip_list
from pip_candidates import tile_pips, denormalize, conns_to_zero_bit_pips, global_bel_suffix

# tile type -> its single LFCPNX-100 instance (from the tilegrid)
INSTANCES = {
    "ECLK_0": "CIB_R74C72:ECLK_0",
    "ECLK_3": "CIB_R74C75:ECLK_3",
    "DLY40": "CIB_R74C70:DLY40",
    "PCLK_DLY_10": "CIB_R36C159:PCLK_DLY_10",
    "PCLK_DLY_20": "CIB_R39C159:PCLK_DLY_20",
    "PCLK_DLY_60": "CIB_R39C0:PCLK_DLY_60",
    "PCLK_DLY_70": "CIB_R36C0:PCLK_DLY_70",
    "DDR_OSC_R": "CIB_R72C159:DDR_OSC_R",
    "BMID_0_ECLK_1": "CIB_R74C73:BMID_0_ECLK_1",
    "BMID_1_ECLK_2": "CIB_R74C74:BMID_1_ECLK_2",
    "DLY50": "CIB_R74C68:DLY50",
    "DLY52": "CIB_R74C69:DLY52",
    "BANKREF4_DLY42_DDR41": "CIB_R74C77:BANKREF4_DLY42_DDR41",
    "DLY30": "CIB_R74C78:DLY30",
    "DLY32": "CIB_R74C79:DLY32",
}

# LIFCL tile type to take the candidates from, where its name differs (on LIFCL-40 the left-edge
# primary clock delay tiles share a tile with an RBB tile: PCLK_DLY_60_RBB_8, PCLK_DLY_70_RBB_6; on
# LFCPNX-100 they are tiles of their own, and RBB_6 / RBB_8 are elsewhere on the left edge)
LIFCL_NAME = {"PCLK_DLY_60": "PCLK_DLY_60_RBB_8", "PCLK_DLY_70": "PCLK_DLY_70_RBB_6",
              # the bottom-edge DLLDELs, which LIFCL-40 has in SYSIO tiles
              "DLY50": "SYSIO_B4_0_DLY50", "DLY52": "SYSIO_B4_1_DLY52", "BANKREF4_DLY42_DDR41": "SYSIO_B4_0_DLY42",
              "DLY30": "SYSIO_B3_0_DLY30_V18", "DLY32": "SYSIO_B3_1_DLY32"}
# of a candidate tile type that is a merged tile on LIFCL, only these arcs (the DLLDEL's)
PIP_FILTER = {tt: (lambda frm, to: any(k in frm + to for k in ("DLLDEL", "_I4_")))
              for tt in ("DLY50", "DLY52", "BANKREF4_DLY42_DDR41", "DLY30", "DLY32")}

# Per tile type: global bel -> R/C of its wires on LFCPNX-100 (found with --locate, 2026-11-11).
# Bel names repeat between tile types (DLY40 and PCLK_DLY_10 both have I4_0..8), so this is
# keyed by tile type.
_ECLK = {
    "_ECLKBANK_CORE_ECLKBANK3": (73, 74), "_ECLKCASMUX_CORE_ECLKCASMUX3": (73, 74),
    "_ECLKBANK_CORE_ECLKBANK4": (73, 73), "_ECLKCASMUX_CORE_ECLKCASMUX4": (73, 73),
    "_ECLKBANK_CORE_ECLKBANK5": (73, 72), "_ECLKCASMUX_CORE_ECLKCASMUX5": (73, 72),
}
GLOBAL_LOCS = {
    "ECLK_0": _ECLK,
    "ECLK_3": _ECLK,
    "BMID_0_ECLK_1": _ECLK,
    "BMID_1_ECLK_2": {**_ECLK, "_BMID_CORE_BMIDMUX": (73, 73), "_ECLKLOGICMUXPLLFB_CORE_ECLKPLLFBR": (73, 75)},
    "DLY40": {"_I4_{}".format(i): (73, 70) for i in range(9)},
    "PCLK_DLY_10": {"_I4_{}".format(i): (36, 158) for i in range(9)},
    # left edge, mirrored (--locate accepted only R39C1 for PCLK_DLY_60's I4 bels, 2026-11-13)
    "PCLK_DLY_60": {"_I4_{}".format(i): (39, 1) for i in range(9)},
    "PCLK_DLY_70": {"_I4_{}".format(i): (36, 1) for i in range(9)},
    # bottom-edge DLLDELs: the I4 code muxes at the DLLDEL's site (R73, the tile's column), as DLY40's
    **{tt: {"_I4_{}".format(i): (73, c) for i in range(9)}
       for tt, c in (("DLY50", 68), ("DLY52", 69), ("BANKREF4_DLY42_DDR41", 77), ("DLY30", 78), ("DLY32", 79))},
}

# Extra fuzz tiles: the ECLK muxes span the bottom-middle tile group, as on LIFCL (150-eclkroute
# fuzzes ECLK_0, BMID_0_ECLK_1, BMID_1_ECLK_2 and ECLK_3 together); e.g. ECLKSYNCM2 -> ECLKOUT2 of
# ECLKCASMUX5 sets a bit in ECLK_0 and one in BMID_0_ECLK_1.
_ECLK_GROUP = ["CIB_R74C72:ECLK_0", "CIB_R74C73:BMID_0_ECLK_1", "CIB_R74C74:BMID_1_ECLK_2", "CIB_R74C75:ECLK_3"]
EXTRA_TILES = {tt: [x for x in _ECLK_GROUP if x != INSTANCES[tt]] for tt in ("ECLK_0", "ECLK_3", "BMID_0_ECLK_1", "BMID_1_ECLK_2")}

# Per tile type: LIFCL wire name -> Lattice name where LFCPNX's layout differs from LIFCL's.
# PCLK_DLY_20's DLLDEL sits at W1 on LFCPNX-100 (R39C158 for tile R39C159), not N1W1 as on
# LIFCL (found by forcing its CLKIN->CLKOUT arc at each R/C near the tile with sv2udb).
OVERRIDES = {
    "PCLK_DLY_20": {
        "N1W1:JCLKIN_DLLDEL_CORE_I0": "R39C158_JCLKIN_DLLDEL_CORE_I0",
        "N1W1:JCLKOUT_DLLDEL_CORE_I0": "R39C158_JCLKOUT_DLLDEL_CORE_I0",
    },
}


def locate(types, chip):
    """For each global bel used by the given tile types, force one of its LIFCL arcs at every R/C in
    a window around the tile and report the R/C(s) that sv2udb accepts."""
    rad = os.environ["RADIANTDIR"]
    env = dict(os.environ, FOUNDRY=rad + "/ispfpga", LM_LICENSE_FILE=rad + "/license/license.dat",
               LD_LIBRARY_PATH=rad + "/bin/lin64:" + rad + "/ispfpga/bin/lin64")
    tmpl = open("../shared/route_100.v").read()
    os.makedirs("work/locate", exist_ok=True)
    for tt in types:
        seen = set()
        tile = INSTANCES[tt]
        r, c = map(int, tile.split(":")[0].split("_R")[1].split("C"))
        for frm, to in sorted(tile_pips("LIFCL", LIFCL_NAME.get(tt, tt))):
            gs = [w for w in (frm, to) if w.startswith("G:")]
            key = global_bel_suffix(gs[0][2:]) if gs else None
            if not gs or key in seen or any(global_bel_suffix(g[2:]) != key for g in gs):
                continue
            seen.add(key)
            hits = []
            for rr in range(max(0, r - 3), r + 2):
                for cc in range(max(0, c - 3), c + 4):
                    locs = {key: (rr, cc)}
                    fa, ta = (denormalize(chip, tile, r, c, w, locs) for w in (frm, to))
                    if len(fa) != 1 or len(ta) != 1:
                        continue
                    v = "work/locate/{}_{}_{}.v".format(re.sub(r"\W", "", key), rr, cc)
                    open(v, "w").write(tmpl.replace("${arcs_attr}", r', \dm:arcs ="{}.{}"'.format(ta[0], fa[0])))
                    p = subprocess.run([rad + "/ispfpga/bin/lin64/sv2udb", "-o", v[:-2] + ".udb", v], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
                    if p.returncode == 0 and "fatal error" not in p.stdout:
                        hits.append((rr, cc))
            print("{} {}: {}".format(tt, key, hits), flush=True)


def main():
    args = sys.argv[1:]
    chip = libpyprjoxide.Chip(libpyprjoxide.Database(database.get_db_root()), "LFCPNX-100")
    if args[:1] == ["--locate"]:
        locate(args[1:] or list(INSTANCES), chip)
        return
    types = args or list(INSTANCES)
    for tt in types:
        tile = INSTANCES[tt]
        r, c = map(int, tile.split(":")[0].split("_R")[1].split("C"))
        pips = []
        for frm, to in sorted(tile_pips("LIFCL", LIFCL_NAME.get(tt, tt)) - (tile_pips("LFCPNX", tt) if have_ron(tt) else set())):
            if tt in PIP_FILTER and not PIP_FILTER[tt](frm, to):
                continue
            ov = OVERRIDES.get(tt, {})
            af, at = ([ov[w]] if w in ov else denormalize(chip, tile, r, c, w, GLOBAL_LOCS.get(tt, {}))
                      for w in (frm, to))
            if len(af) != 1 or len(at) != 1:
                print("UNMAPPED {} {} -> {}: {} -> {}".format(tt, frm, to, af, at), flush=True)
                continue
            pips.append((af[0], at[0]))
        print("{}: {} candidates".format(tt, len(pips)), flush=True)
        if not pips:
            continue
        cfg = FuzzConfig(job=tt, device="LFCPNX-100", sv="../shared/route_100.v", tiles=[tile] + EXTRA_TILES.get(tt, []))
        cfg.setup(skip_specimen=True)
        fuzz_pip_list(cfg, pips, ignore_tiles=row_tap_tiles(tile))
    for tt in types:
        conns_to_zero_bit_pips(tt, ref_tt=LIFCL_NAME.get(tt, tt))


def row_tap_tiles(tile):
    """TAP tiles on the tile's row. Clock tile arcs also set a bit in the row's clock TAP
    (branch) tile; without ignoring those the solver drops every such sample."""
    import json
    from os import path
    row = re.search(r"_R(\d+)C", tile).group(1)
    grid = json.load(open(path.join(database.get_db_root(), "LFCPNX", "LFCPNX-100", "tilegrid.json")))
    tiles = grid.get("tiles", grid)
    return {t for t in tiles if t.startswith("TAP_") and re.search(r"_R{}C\d+:".format(row), t)}


def have_ron(tt):
    from os import path
    return path.exists(path.join(database.get_db_root(), "LFCPNX", "tiletypes", tt + ".ron"))


if __name__ == "__main__":
    main()
