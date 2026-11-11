#!/usr/bin/env python3
"""Derive CertusPro-NX (LFCPNX) GPLL_LLC and GPLL_URC routing from CrossLink-NX's.

ULC and LRC match CrossLink-NX exactly (Radiant routing, 2026-11-11) and need
nothing. LLC and URC differ, as below. Both results were confirmed on silicon
(all four corners lock at 100 MHz from P24 on the LFCPNX-100 Versa board).

LLC:
Radiant's routing of an LLC PLL test, decoded against LIFCL's GPLL tiles
(2026-11-11), shows that the LFCPNX-100 LLC PLL sits one row lower relative to
its GPLL tile than on LIFCL-40:
  LIFCL-40:   GPLL_LLC R55C0, CIB_LR R54C1 (N1E1), CIB R55C1 (E1), MIB_B R56
  LFCPNX-100: GPLL_LLC R72C0, CIB_LR R72C1 (E1),   CIB R73C1 (S1E1), MIB_B R74
Radiant ties PLLRESET at R72C1 JLSR1 (LIFCL: N1E1:JLSR1) and takes LOCK from
R73C1 JF1 (LIFCL: E1:JF1). So every tile-relative wire moves one row south.

Pad-fed reference inputs follow each device's own floorplan; those Radiant
was seen to use are listed in KNOWN_PADS, and the rest are left out.

URC: CrossLink-NX has no upper right PLL. Its tile is CrossLink-NX's GPLL_LRC
flipped north/south (Radiant: PLLRESET at S1W1:JLSR0, LOCK at W1:JF1), with
UR clock names (CLKOP reaches RMID as JURCLKOP), the bottom-edge ECLK links
dropped and REFCLK14 fed from pad PR4A (S3). Other pad inputs are left out.

Usage: derive_gpll_tiles.py <prjoxide database root> <LFCPNX CRAM .ron dir> <out dir>
  (reads LIFCL/tiletypes/GPLL_{LLC,LRC}.ron and <dir>/GPLL_{LLC,URC}.ron, writes
   <out dir>/GPLL_LLC.ron and GPLL_URC.ron)
"""
import json
import re
import sys

import os

ROW_SHIFT = 1  # LLC: rows south
REACH = 4      # tiles from the PLL tile a borrowed connection may reach
# Observed in Radiant routing (radiant-fuzz/pll-conns/conns_summary.txt); keys
# are LIFCL's names, values are LFCPNX wires relative to the LFCPNX tile.
# REFCLK15 and REFCLK25 were not exercised, so they are left out.
LLC_PADS = {
    "E1:JREFCLK13_REFMUX_CORE_REFMUX": ["N30:JPADDI_SEIO33_CORE_IOA"],    # PL42A, P24
    "E1:JREFCLK14_REFMUX_CORE_REFMUX": ["S2E2:JPADDI_DIFFIO18_CORE_IOA"],  # PB2A
    "E1:JREFCLK16_REFMUX_CORE_REFMUX": ["S2E4:JPADDI_DIFFIO18_CORE_IOA"],  # PB4A
    "E1:JREFCLK23_REFMUX_CORE_REFMUX": ["N28:JPADDI_SEIO33_CORE_IOA"],    # PL44A
    "E1:JREFCLK26_REFMUX_CORE_REFMUX": ["S2E10:JPADDI_DIFFIO18_CORE_IOA"], # PB10A
}
URC_PADS = {
    "W1:JREFCLK14_REFMUX_CORE_REFMUX": ["S3:JPADDI_SEIO33_CORE_IOA"],  # PR4A
}


def is_pad(wire):
    return "PADDI" in wire or "JINCK" in wire


def ron_to_py(text):
    text = re.sub(r"(?<=[\s(,])([a-z_]+):", r'"\1":', text)
    text = text.replace("(", "{").replace(")", "}")
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def py_to_ron(v, ind=0):
    pad = "  " * ind
    if isinstance(v, dict):
        if not v:
            return "{}"
        # structs (field names are lowercase identifiers) use ( ), maps use { }
        is_struct = all(re.fullmatch(r"[a-z_]+", k) for k in v)
        open_, close = ("(", ")") if is_struct else ("{", "}")
        items = []
        for k, x in v.items():
            key = k if is_struct else json.dumps(k)
            items.append(f"{pad}  {key}: {py_to_ron(x, ind + 1)},")
        return open_ + "\n" + "\n".join(items) + "\n" + pad + close
    if isinstance(v, list):
        if not v:
            return "[]"
        return "[\n" + "\n".join(f"{pad}  {py_to_ron(x, ind + 1)}," for x in v) + "\n" + pad + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v)
    return str(v)


def parse_step(step):
    """'N1E1' -> (dy, dx) with south and east positive."""
    dy = dx = 0
    for d, n in re.findall(r"([NSEW])(\d+)", step):
        n = int(n)
        if d == "N": dy -= n
        if d == "S": dy += n
        if d == "E": dx += n
        if d == "W": dx -= n
    return dy, dx


def fmt_step(dy, dx):
    s = ""
    if dy < 0: s += f"N{-dy}"
    if dy > 0: s += f"S{dy}"
    if dx > 0: s += f"E{dx}"
    if dx < 0: s += f"W{-dx}"
    return s


def is_near(wire):
    if ":" not in wire:
        return True
    step, _ = wire.split(":", 1)
    if step == "G":
        return True
    dy, dx = parse_step(step)
    return abs(dy) <= REACH and abs(dx) <= REACH


def llc_wire(wire):
    if ":" not in wire:
        return wire
    step, name = wire.split(":", 1)
    if step == "G":
        return wire
    dy, dx = parse_step(step)
    new = fmt_step(dy + ROW_SHIFT, dx)
    return f"{new}:{name}" if new else name


def urc_wire(wire):
    """GPLL_LRC wire -> GPLL_URC wire; None for links URC lacks."""
    if ":" not in wire:
        return wire
    step, name = wire.split(":", 1)
    if step == "G":
        if "ECLK" in name:
            return None
        return "G:" + name.replace("JLRCLKO", "JURCLKO", 1).replace("BMID", "TMID")
    return step.translate(str.maketrans("NS", "SN")) + ":" + name


def derive(lifcl, own, transform, pads):
    pips = {}
    for dst, arcs in lifcl["pips"].items():
        d = transform(dst)
        if d is None:
            continue
        kept = []
        for a in arcs:
            f = transform(a["from_wire"])
            if f is not None:
                kept.append(dict(a, from_wire=f))
        if kept:
            pips[d] = kept
    conns = {}
    for dst, cs in lifcl["conns"].items():
        if dst in pads:
            conns[transform(dst)] = [{"from_wire": w} for w in pads[dst]]
            continue
        d = transform(dst)
        if d is None or not is_near(dst):
            continue
        kept = []
        for c in cs:
            # pad inputs follow each device's floorplan: only observed ones
            if is_pad(c["from_wire"]) or not is_near(c["from_wire"]):
                continue
            f = transform(c["from_wire"])
            if f is not None:
                kept.append(dict(c, from_wire=f))
        if kept:
            conns[d] = kept
    own = dict(own)
    own["pips"] = pips
    own["conns"] = conns
    return own


def main(db_root, own_dir, out_dir):
    read = lambda p: ron_to_py(open(p).read())
    lifcl = os.path.join(db_root, "LIFCL", "tiletypes")
    for corner, source, transform, pads in [
        ("LLC", "GPLL_LLC", llc_wire, LLC_PADS),
        ("URC", "GPLL_LRC", urc_wire, URC_PADS),
    ]:
        db = derive(
            read(os.path.join(lifcl, f"{source}.ron")),
            read(os.path.join(own_dir, f"GPLL_{corner}.ron")),
            transform,
            pads,
        )
        out = os.path.join(out_dir, f"GPLL_{corner}.ron")
        open(out, "w").write(py_to_ron(db) + "\n")
        print(f"{out}: {len(db['pips'])} pip destinations, {len(db['conns'])} conns")


if __name__ == "__main__":
    main(*sys.argv[1:4])
