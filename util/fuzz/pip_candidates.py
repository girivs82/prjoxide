"""
Helpers for fuzzing pips taken from another family's database (no lapie):
candidate lists from tile .ron files, translation of normalised tile-relative wire names
to Lattice absolute names, and storing zero-bit mux options the way the reference does.
"""
import re
from os import path

import database


def tile_pips(family, tiletype):
    t = open(path.join(database.get_db_root(), family, "tiletypes", tiletype + ".ron")).read()
    s = t[t.index("  pips:"):t.index("  words:")]
    pips = set()
    for m in re.finditer(r'\n    "([^"]+)": \[(.*?)\n    \],', s, re.S):
        for fw in re.findall(r'from_wire: "([^"]+)"', m.group(2)):
            pips.add((fw, m.group(1)))
    return pips


def global_bel_suffix(name):
    """The bel part of a global wire name: JMUXIN2_ECLKBANK_CORE_ECLKBANK5 -> _ECLKBANK_CORE_ECLKBANK5."""
    return re.sub(r'^J?[A-Z0-9]+?_', '_', name, count=1)


def denormalize(chip, tile, r, c, rel, global_locs=None):
    """Lattice absolute names whose prjoxide normalisation in `tile` is `rel`."""
    if rel.startswith("G:"):
        # Global wire: prjoxide names it G:<name> whatever its R/C, so normalize_wire cannot locate
        # it. The caller supplies where each global bel lives (global_locs: bel suffix -> (r, c)).
        base = rel[2:]
        loc = (global_locs or {}).get(global_bel_suffix(base))
        return ["R{}C{}_{}".format(loc[0], loc[1], base)] if loc else []
    m = re.match(r'^(?:([NSEW]\d+(?:[NSEW]\d+)?):)?(.+)$', rel)
    pre, base = m.group(1), m.group(2)
    dr = dc = 0
    for d, n in re.findall(r'([NSEW])(\d+)', pre or ""):
        n = int(n)
        dr += {"N": -n, "S": n}.get(d, 0)
        dc += {"E": n, "W": -n}.get(d, 0)
    bases = [base]
    mm = re.match(r'^([HV]0[26][NSEW]\d\d)(\d\d)$', base)
    if mm:
        bases = [mm.group(1) + "{:02}".format(i) for i in range(4)]
    found = []
    for b in bases:
        for rr in range(r + dr - 3, r + dr + 4):
            for cc in range(c + dc - 3, c + dc + 4):
                if rr < 0 or cc < 0:
                    continue
                cand = "R{}C{}_{}".format(rr, cc, b)
                try:
                    if chip.normalize_wire(tile, cand) == rel:
                        found.append(cand)
                except BaseException:
                    pass
    if len(found) > 1:
        # Several aliases can normalise to the same name. At the top edge both R1C18_V02N0700 and
        # R0C18_V02N0701 give N1:V02N0701; Radiant only accepts the one named at the tile's own
        # location (row 0 has no V02N wires), so prefer that, then the literal name at the
        # prefix's location.
        own = [w for w in found if w.startswith("R{}C{}_".format(r, c))]
        if len(own) == 1:
            return own
        exact = "R{}C{}_{}".format(r + dr, c + dc, base)
        if exact in found:
            return [exact]
    return found


def conns_to_zero_bit_pips(tt, family="LFCPNX", ref_family="LIFCL"):
    """A forced arc that changes no bits is stored by the pip solver as a fixed connection. Where the reference family
    has that arc as an empty-bit pip (the zero-bit option of a mux, e.g. EBOUNCE -> H00R0000) and the
    sink has configurable pips in the LFCPNX tile too, store it as the reference does: a pip with no bits."""
    root = database.get_db_root()
    lifcl = open(path.join(root, ref_family, "tiletypes", tt + ".ron")).read()
    fn = path.join(root, family, "tiletypes", tt + ".ron")
    if not path.exists(fn):
        return
    t = open(fn).read()
    block = re.compile(r'\n    "([^"]+)": \[(.*?)\n    \],', re.S)
    lp = lifcl[lifcl.index("  pips:"):lifcl.index("  words:")]
    zero = {(fw, m.group(1)) for m in block.finditer(lp)
            for fw in re.findall(r'from_wire: "([^"]+)",\s*bits: \[\],', m.group(2))}
    head, rest = t[:t.index("  pips:")], t[t.index("  pips:"):]
    pips_s, mid, conns_s = rest[:rest.index("  words:")], rest[rest.index("  words:"):rest.index("  conns:")], rest[rest.index("  conns:"):]
    conns = [(m.group(1), fw) for m in block.finditer(conns_s) for fw in re.findall(r'from_wire: "([^"]+)"', m.group(2))]
    moved = [(fw, to) for to, fw in conns
             if (fw, to) in zero and re.search(r'\n    "{}": \['.format(re.escape(to)), pips_s)]
    if not moved:
        return
    for fw, to in moved:
        m = re.search(r'\n    "{}": \[\n'.format(re.escape(to)), pips_s)
        entry = '      (\n        from_wire: "{}",\n        bits: [],\n      ),\n'.format(fw)
        pips_s = pips_s[:m.end()] + entry + pips_s[m.end():]
    keep = {}
    for to, fw in conns:
        if (fw, to) not in moved:
            keep.setdefault(to, []).append(fw)
    if keep:
        conns_s = "  conns: {\n" + "".join('    "{}": [\n{}    ],\n'.format(
            to, "".join('      (\n        from_wire: "{}",\n      ),\n'.format(fw) for fw in fws))
            for to, fws in sorted(keep.items())) + "  },\n)"
    else:
        conns_s = "  conns: {},\n)"
    open(fn, "w").write(head + pips_s + mid + conns_s)
    print("{}: {} fixed conns stored as zero-bit pips: {}".format(tt, len(moved), moved), flush=True)
