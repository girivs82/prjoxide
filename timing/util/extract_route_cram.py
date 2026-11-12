"""
Build the routed (source pin, sink pin) -> pips map that solve_interconnect.py needs, from
Radiant's user-facing outputs only (no lapie / udb access):

  - the pips: the routed design's readback bitstream, decoded to FASM by prjoxide
    (`prjoxide unpack`), with tile-relative wire names turned into one key per routing node;
  - cell placement: Radiant timing reports (`timing -sethld ... -o x.twr`), which give the
    site of every cell on each reported path, and par's .pad file for IO cells;
  - SDF cell names: the backannotated Verilog (.vo), which lists the logical members of each
    SDF cell (a SLICE, IO, ...), as named in the timing report;
  - the arcs to trace: the SDF INTERCONNECT entries.

Each SDF interconnect arc is traced backwards from the sink pin's wire through the decoded
pips (falling back to the tile types' fixed connections and zero-bit pips, which leave no bits
in the bitstream) until the source pin's wire is reached.

Output pickle: dict(arc2pips={((src_cell, src_pin), (dst_cell, dst_pin)): [(wireA, wireB), ...]},
wire_fanout={wire: count}) with wires named R<row>C<col>_<name> as solve_interconnect expects
(global clock wires that have no single location are given a representative one).

Usage: extract_route_cram.py design.fasm design.vo design.sdf par.pad out.pickle report.twr [...]
"""
import json
import pickle
import re
import sys
from collections import defaultdict
from os import path

import database
from parse_sdf import parse_sdf_file

FAMILY = "LFCPNX"
DEVICE = "LFCPNX-100"

DIR_RE = re.compile(r'^(?:([NS])(\d+))?(?:([EW])(\d+))?$')
TILE_RC_RE = re.compile(r'R(\d+)C(\d+)')
SITE_RE = re.compile(r'^(?:SLICE_)?R(\d+)C(\d+)([A-D])$')
PIO_RE = re.compile(r'^P([LRTB])(\d+)([A-D])$')


# ---------------------------------------------------------------------------------------------
# Device: tile grid and tile type data
# ---------------------------------------------------------------------------------------------

class Device:
    def __init__(self, family, device):
        root = database.get_db_root()
        grid = json.load(open(path.join(root, family, device, "tilegrid.json")))
        grid = grid.get("tiles", grid)
        self.family = family
        self.tiles_at = defaultdict(list)       # (r, c) -> [tiletype]
        self.tile_name = {}                     # (r, c, tiletype) -> tilegrid name
        self.tiles_of = defaultdict(list)       # tiletype -> [(r, c)]
        self.taps = defaultdict(list)           # row -> [tap col]
        self.max_row = self.max_col = 0
        for name in grid:
            tname, tt = name.split(":")
            r, c = map(int, TILE_RC_RE.search(tname).groups())
            self.tiles_at[r, c].append(tt)
            self.tile_name[r, c, tt] = name
            self.tiles_of[tt].append((r, c))
            self.max_row, self.max_col = max(self.max_row, r), max(self.max_col, c)
            if tt.startswith("TAP_"):
                self.taps[r].append(c)
        for r in self.taps:
            self.taps[r].sort()
        self.spine_rows = sorted({r for tt, locs in self.tiles_of.items() if tt.startswith("SPINE_") for r, _ in locs})
        self.center_col = (self.max_col + 1) // 2
        self._tt_cache = {}
        self._by_dst = None
        self._chip = None
        self._denorm = {}

    EDGE_MARGIN = 6

    def near_edge(self, r, c):
        m = self.EDGE_MARGIN
        return r <= m or c <= m or r >= self.max_row - m or c >= self.max_col - m

    def lattice_name(self, r, c, tt, rel):
        """At the device edges prjoxide regularises Lattice's clamped wire names relative to the
        tile doing the normalising, so the same node can get different regular names from
        different tiles. There, recover the real Lattice name with prjoxide's normalize_wire as
        the oracle; returns (row, col, name) or None if not unique."""
        ck = (r, c, tt, rel)
        if ck not in self._denorm:
            if self._chip is None:
                import libpyprjoxide
                self._chip = libpyprjoxide.Chip(libpyprjoxide.Database(database.get_db_root()), DEVICE)
            from pip_candidates import denormalize
            found = denormalize(self._chip, self.tile_name[r, c, tt], r, c, rel.replace("__", ":", 1))
            res = None
            if len(found) == 1:
                rr, cc, n = re.match(r'^R(\d+)C(\d+)_(.+)$', found[0]).groups()
                res = (int(rr), int(cc), n)
            self._denorm[ck] = res
        return self._denorm[ck]

    def tiletype(self, tt, family=None):
        """(pips, conns) of a tile type: lists of (to_wire, from_wire, has_bits)."""
        family = family or self.family
        if (family, tt) not in self._tt_cache:
            fn = path.join(database.get_db_root(), family, "tiletypes", tt + ".ron")
            pips, conns = [], []
            if path.exists(fn):
                s = open(fn).read()
                pi, ci = s.find("\n  pips:"), s.find("\n  conns:")
                for start, out in ((pi, pips), (ci, conns)):
                    if start < 0:
                        continue
                    ends = [x for x in (pi, ci, s.find("\n  words:"), s.find("\n  enums:")) if x > start]
                    body = s[start:min(ends) if ends else len(s)]
                    for to, entries in re.findall(r'\n    "([^"]+)": \[(.*?)\n    \],', body, re.S):
                        for fw, rest in re.findall(r'from_wire: "([^"]+)",(.*?)\n      \)', entries, re.S):
                            inv = re.findall(r'invert:(\w+)', rest)
                            # "zero": the option sets no bits at all (no bits, or only bits that
                            # must be clear); these never appear in prjoxide's FASM output
                            out.append((to, fw, bool(inv) and "false" in inv))
            self._tt_cache[family, tt] = (pips, conns)
        return self._tt_cache[family, tt]

    # Tile types whose LFCPNX database has no routing at all yet (the EBR, LRAM and DSP tiles'
    # connections between CIB wires and the block's core pins); for these the LIFCL tile type of
    # the same name supplies candidate arcs, all treated as setting no bits. An arc traced
    # through one is only accepted if the trace reaches the SDF source pin (kind "ref").
    REF_FAMILY = "LIFCL"

    def by_dst(self):
        """dst wire base name -> [(tiletype, dst_rel, src_rel, kind)] for fixed conns and zero-bit
        pips, the arcs that leave no bits in the bitstream."""
        if self._by_dst is None:
            self._by_dst = defaultdict(list)
            self.ref_types = set()
            for tt in self.tiles_of:
                pips, conns = self.tiletype(tt)
                if not pips and not conns:
                    rp, rc = self.tiletype(tt, self.REF_FAMILY)
                    if rp or rc:
                        self.ref_types.add(tt)
                        for to, fw, bits in rp + rc:
                            self._by_dst[split_rel(to)[1]].append((tt, to, fw, "ref"))
                    continue
                for to, fw, bits in conns:
                    self._by_dst[split_rel(to)[1]].append((tt, to, fw, "conn"))
                for to, fw, bits in pips:
                    if not bits:
                        self._by_dst[split_rel(to)[1]].append((tt, to, fw, "zero"))
        return self._by_dst

    # -- global clock network segment keys ------------------------------------------------------
    def tap_side(self, r, c):
        """The TAP (column, side) that drives the HPBX branch wires of tile (r, c)."""
        taps = self.taps.get(r) or self.taps[min(self.taps, key=lambda x: abs(x - r))]
        tc = min(taps, key=lambda t: (abs(t - c), t))
        return tc, ("L" if c < tc else "R")

    def half(self, r):
        return "T" if r < (self.spine_rows[0] + self.spine_rows[-1] + 1) // 2 else "B"

    def spine_tap(self, c):
        cols = sorted({cc for cc in self.taps[next(iter(self.taps))]})
        return min(cols, key=lambda t: (abs(t - c), -t))


def split_rel(w):
    if "__" in w and ":" not in w:
        w = w.replace("__", ":", 1)
    if ":" in w:
        p, n = w.split(":", 1)
        return p, n
    return "", w


def wire_key(dev, r, c, tt, rel):
    """Canonical key of the routing node that tile type `tt` at (r, c) calls `rel`."""
    p, n = split_rel(rel)
    m = DIR_RE.match(p)
    if m:
        ns, nd, ew, ed = m.groups()
        dr = (int(nd) if ns == "S" else -int(nd)) if ns else 0
        dc = (int(ed) if ew == "E" else -int(ed)) if ew else 0
        return ("W", r + dr, c + dc, n)
    if p == "G":
        return ("G", n)
    if p in ("BRANCH_L", "BRANCH_R"):
        return ("HPBX", r, c, p[-1], n)
    if p == "BRANCH":
        tc, side = dev.tap_side(r, c)
        return ("HPBX", r, tc, side, n)
    if p == "SPINE":
        return ("VPSX", dev.half(r), dev.spine_tap(c), n)
    if p == "HROW":
        return ("HPRX", dev.half(r), "L" if c < dev.center_col else "R", n)
    return ("X", p, r, c, n)


def key_name(dev, k, io_alias={}):
    """R<r>C<c>_<name> wire name for solve_interconnect's classify_pip."""
    if k in io_alias:
        return io_alias[k]
    if k[0] == "W":
        return "R{}C{}_{}".format(k[1], k[2], k[3])
    if k[0] == "G":
        return "R0C0_{}".format(k[1])
    if k[0] == "HPBX":
        return "R{}C{}_{}".format(k[1], k[2], k[4])
    if k[0] == "VPSX":
        return "R{}C{}_{}".format(dev.spine_rows[0 if k[1] == "T" else -1], k[2], k[3])
    if k[0] == "HPRX":
        return "R{}C{}_{}".format(dev.spine_rows[0 if k[1] == "T" else -1],
                                  1 if k[2] == "L" else dev.max_col - 1, k[3])
    return "R{}C{}_{}".format(k[2], k[3], k[4])


# ---------------------------------------------------------------------------------------------
# Routing graph from the decoded bitstream
# ---------------------------------------------------------------------------------------------

class Routing:
    def __init__(self, dev, fasm):
        self.dev = dev
        self.drv = defaultdict(set)   # dst key -> {src key} from pips with bits set
        self.used = set()
        for line in open(fasm):
            line = line.strip()
            if ".PIP." not in line:
                continue
            tile, _, rest = line.partition(".PIP.")
            tname, tt = tile.split("__", 1)
            r, c = map(int, TILE_RC_RE.search(tname).groups())
            to, frm = self._split_pip(rest)
            dk, sk = wire_key(dev, r, c, tt, to), wire_key(dev, r, c, tt, frm)
            self.drv[dk].add(sk)
            self.used.update((dk, sk))
        self._fixed = {}
        self.alias = set()
        self.ref_edges = set()   # arcs taken from the reference family's tile types
        self.extra = defaultdict(set)   # dst key -> {src key}: IO pad arcs added by pin_keys

    @staticmethod
    def _split_pip(rest):
        # "<to>.<from>"; wire names never contain '.'
        to, frm = rest.split(".")
        return to, frm

    def fixed_drivers(self, k):
        """Drivers of key k through arcs that set no bits: [(src key, kind)]."""
        if k in self._fixed:
            return self._fixed[k]
        dev = self.dev
        name = k[-1]
        out = []
        for tt, to, fw, kind in dev.by_dst().get(name, ()):
            p, _ = split_rel(to)
            m = DIR_RE.match(p)
            if k[0] == "W" and m:
                ns, nd, ew, ed = m.groups()
                dr = (int(nd) if ns == "S" else -int(nd)) if ns else 0
                dc = (int(ed) if ew == "E" else -int(ed)) if ew else 0
                locs = [(k[1] - dr, k[2] - dc)]
            elif k[0] != "W" and not m:
                locs = dev.tiles_of[tt]
            else:
                continue
            for (r, c) in locs:
                if tt in dev.tiles_at.get((r, c), ()) and wire_key(dev, r, c, tt, to) == k:
                    out.append((wire_key(dev, r, c, tt, fw), kind))
        # HROW HPRX wires are fed from the CMUX trunks' {T,B}{L,R}HPRX<n> globals; the LFCPNX
        # SPINE tile types do not carry those arcs (they set no bits).
        if k[0] == "HPRX":
            m = re.match(r'^HPRX(\d\d)00$', k[3])
            if m:
                out.append((("G", "{}{}HPRX{}".format(k[1], k[2], int(m.group(1)))), "conn"))
        self._fixed[k] = out
        return out

    def drivers(self, k):
        """Possible drivers of node k in this design: the pip(s) with bits set if there are any
        (they are authoritative), otherwise the arcs that leave no bits (fixed connections
        and zero-bit pips), otherwise an edge alias (see edge_aliases)."""
        if k in self.drv:
            return sorted(self.drv[k])
        if k in self.extra:
            return sorted(self.extra[k])
        fd = self.fixed_drivers(k)
        for s_, kind in fd:
            if kind == "ref":
                self.ref_edges.add((s_, k))
        fixed = [s_ for s_, _ in fd]
        if fixed:
            return fixed
        if k[0] == "W" and k[3].endswith("_CIBTEST"):
            return self.cibtest_aliases(k)
        return self.edge_aliases(k)

    def cibtest_aliases(self, k):
        """On LFCPNX a hard block's output (EBR, LRAM, DSP) reaches a CIB wire Jxx through that
        CIB's Jxx_CIBTEST input and a Jxx <- Jxx_CIBTEST pip, as pad inputs do; LIFCL's tile
        types connect the block's pin straight to Jxx. So Jxx_CIBTEST is the block pin under
        another name: its drivers are the block pins connected to Jxx."""
        base = ("W", k[1], k[2], k[3][:-len("_CIBTEST")])
        out = []
        for s_, kind in self.fixed_drivers(base):
            if s_ != k and kind in ("conn", "ref"):
                out.append(s_)
                self.alias.add((s_, k))
                if kind == "ref":
                    self.ref_edges.add((s_, k))
        return out

    EDGE_WIRE_RE = re.compile(r'^([HV])(0[126])([NSEW])(\d{4})$')
    FLIP = {"N": "S", "S": "N", "E": "W", "W": "E"}

    def edge_aliases(self, k):
        """Wires that run into the device edge turn round: an eastbound H02/H06 driven next to the
        right edge comes back as the westbound wire with the same track, and likewise W at the
        left edge and N/S at the top and bottom. With prjoxide's regularised names the two names
        mirror about the edge: their positions along the wire's axis add up to 1 at the left/top
        edge and to 2*max-1 at the right/bottom edge (e.g. R36C158 E1:H02E0501 = R36C159
        H02E0501 drives R36C157 E1:H02W0501 = R36C158 H02W0501; R1C154 N3:V06N0203 = R-2C154
        V06N0203 drives R3C154 V06S0203). For an undriven H/V wire near an edge, return the
        mirrored wire if a set pip drives it. This is one node under two names, not a pip
        (see self.alias)."""
        if k[0] != "W" or not self.dev.near_edge(k[1], k[2]):
            return []
        m = self.EDGE_WIRE_RE.match(k[3])
        if not m:
            return []
        hv, span, d, track = m.groups()
        flipped = hv + span + self.FLIP[d] + track
        dev = self.dev
        if hv == "H":
            pos, top = k[2], dev.max_col
        else:
            pos, top = k[1], dev.max_row
        total = 1 if pos <= dev.EDGE_MARGIN else 2 * top - 1
        a = ("W", k[1], total - pos, flipped) if hv == "H" else ("W", total - pos, k[2], flipped)
        if a in self.drv:
            self.alias.add((a, k))
            return [a]
        return []

    def trace(self, sink, sources, max_nodes=20000):
        """Shortest backwards path from `sink` to one of `sources` (a set of keys, or a predicate
        on keys), as [(src key, dst key)] in source->sink order, or None."""
        is_src = sources if callable(sources) else sources.__contains__
        parent = {sink: None}
        frontier = [sink]
        while frontier and len(parent) < max_nodes:
            nxt = []
            for cur in frontier:
                if is_src(cur):
                    out = []
                    while parent[cur] is not None:
                        out.append((cur, parent[cur]))
                        cur = parent[cur]
                    return out
                for s in self.drivers(cur):
                    if s not in parent:
                        parent[s] = cur
                        nxt.append(s)
            frontier = nxt
        return None


# ---------------------------------------------------------------------------------------------
# Netlist (.vo), placement (.twr, .pad) and pin -> wire mapping
# ---------------------------------------------------------------------------------------------

def unescape(name):
    name = name.strip()
    if name.startswith("\\"):
        name = name[1:]
    return name.replace("\\", "")


def parse_vo(fn):
    """(member logical name -> top-level SDF cell, top-level cell -> top port names)"""
    text = open(fn).read()
    modules, bodies = {}, {}
    for m in re.finditer(r'^module (\S+) \((.*?)\);(.*?)^endmodule', text, re.S | re.M):
        name, body = m.group(1), m.group(3)
        bodies[name] = body
        body = body.split("specify")[0]
        members = re.findall(r'^\s+\S+\s+(\\\S+ |[A-Za-z_][\w$]*)\s*\(', body, re.M)
        modules[name] = [unescape(x) for x in members]
    # the top module is named after the design (top, top_large, ...): the largest module, as it
    # instantiates every cell
    top_name = max(bodies, key=lambda n: len(bodies[n]))
    top = bodies[top_name]
    del modules[top_name]
    member2cell, cell2ports = {}, {}
    for m in re.finditer(r'^\s+(\S+)\s+(\\\S+ |[A-Za-z_][\w$\[\]]*)\s*\((.*?)\);', top, re.S | re.M):
        mod, inst, conns = m.group(1), unescape(m.group(2)), m.group(3)
        if mod not in modules:
            continue
        for mem in modules[mod]:
            member2cell[mem] = inst
        member2cell.setdefault(inst, inst)
        cell2ports[inst] = [unescape(x) for p, x in re.findall(r'\.(\w+)\(([^()]*)\)', conns)
                            if p not in ("PADDI", "PADDO", "PADDT")]
    return member2cell, cell2ports


def parse_twr(fns, member2cell):
    """SDF cell -> site, from the Cell/Site column (and Path Begin/End lines) of timing reports."""
    site = {}
    site_tok = re.compile(r'^(SLICE_R\d+C\d+[A-D]|[A-Z][A-Z0-9]*_R\d+C\d+\w*|(?:SEIO|DIFFIO)\w+)$')

    def add(name, s):
        inst = name.split("->")[0].rsplit("/", 1)[0]
        for cand in (inst, inst.rsplit(".", 1)[0]):
            if cand in member2cell:
                cell = member2cell[cand]
                if site.get(cell, s) != s:
                    raise ValueError("conflicting sites for {}: {} {}".format(cell, site[cell], s))
                site[cell] = s
                return

    for fn in fns:
        lines = open(fn).read().splitlines()
        for i, line in enumerate(lines):
            m = re.match(r'^Path (?:Begin|End)\s*: (\S+)\s+\((\S+)\)', line)
            if m and m.group(2) != "top":
                add(m.group(1), m.group(2))
                continue
            toks = line.split()
            if not toks or "/" not in toks[0] or line[0].isspace():
                continue
            if len(toks) > 1 and site_tok.match(toks[1]):
                add(toks[0], toks[1])
            elif len(toks) == 1 and i + 1 < len(lines) and lines[i + 1][:1].isspace():
                nt = lines[i + 1].split()
                if nt and site_tok.match(nt[0]):
                    add(toks[0], nt[0])
    return site


def parse_pad(fn):
    """(port -> PIO site, package pin -> PIO site) from par's .pad report."""
    port2site, pin2site = {}, {}
    for line in open(fn):
        f = [x.strip() for x in line.split("|")]
        if len(f) > 5 and PIO_RE.match(f[4]):
            port2site[f[1]] = f[4]
            pin2site[f[2].split("/")[0]] = f[4]
    return port2site, pin2site


def pio_loc(dev, pio):
    side, n, letter = PIO_RE.match(pio).groups()
    n = int(n)
    r, c = {"L": (n, 0), "R": (n, dev.max_col), "T": (0, n), "B": (dev.max_row, n)}[side]
    return r, c, letter


def pio_cib(dev, pio):
    """The CIB next to a PIO, through which its pad wires reach the fabric."""
    side = PIO_RE.match(pio).group(1)
    r, c, _ = pio_loc(dev, pio)
    return {"L": (r, 1), "R": (r, dev.max_col - 1), "T": (1, c), "B": (dev.max_row - 1, c)}[side]


def pio_core(dev, pio):
    """IO bel type of a PIO: banks 3-5 are the 1.8V HP banks (DIFFIO18 on A, SEIO18 on B)."""
    r, c, letter = pio_loc(dev, pio)
    for tt in dev.tiles_at.get((r, c), ()):
        m = re.match(r'^SYSIO_B(\d+)', tt)
        if m:
            if int(m.group(1)) in (3, 4, 5):
                return "DIFFIO18" if letter == "A" else "SEIO18"
            return "SEIO33"
    return "SEIO33"


SLICE_PIN_WIRES = {"CLK": "JCLK_SLICE{s}", "LSR": "JLSR_SLICE{s}", "CE": "JCE_SLICE{s}",
                   "SEL": "JSEL_SLICE{s}", "FCI": "JFCI_SLICE{s}", "FCO": "JFCO_SLICE{s}",
                   "WCK": "JWCK_SLICE{s}", "WRE": "JWRE_SLICE{s}"}

# A PIO's pad input enters the fabric at a CIBTEST wire of the next CIB (A: JF5, B: JQ5), found
# from routed designs: every input pad's route starts there.
PADDI_CIBTEST = {"A": "JF5_CIBTEST", "B": "JQ5_CIBTEST"}


def pin_keys(dev, cell_site, pin, routing, io_alias):
    """Candidate wire keys for an SDF cell pin at its site."""
    m = SITE_RE.match(cell_site)
    if m:
        r, c, s = int(m.group(1)), int(m.group(2)), m.group(3)
        w = SLICE_PIN_WIRES.get(pin, "J{p}_SLICE{s}").format(p=pin, s=s)
        return {("W", r, c, w)}
    gm = re.match(r'^([A-Z0-9_]+?)_R(\d+)C(\d+)$', cell_site)
    if gm and not PIO_RE.match(cell_site):
        # hard blocks: the timing report names sites <TYPE>_<TYPE>_R<r>C<c> (e.g.
        # EBR_CORE_EBR_CORE_R10C111); the block's pin wires are J<pin>_<TYPE> at that location
        pre, r, c = gm.group(1), int(gm.group(2)), int(gm.group(3))
        h = len(pre) // 2
        btype = pre[:h] if len(pre) % 2 == 1 and pre[:h] == pre[h + 1:] else pre
        return {("W", r, c, "J{}_{}".format(pin, btype))}
    pm = PIO_RE.match(cell_site)
    if pm:
        r, c, letter = pio_loc(dev, cell_site)
        cr, cc = pio_cib(dev, cell_site)
        bel = "J{}_{}_CORE_IO{}".format(pin, pio_core(dev, cell_site), letter)
        if pin == "PADDI":
            keys = {("W", cr, cc, PADDI_CIBTEST[letter])}
        elif pin == "PADDO":
            # the pad output bel wire, driven from a CIBMUX output as the SYSIO tile type says
            # (per tile type: e.g. pad B from CIBMUXOUTB4 or CIBMUXOUTC0)
            pk = ("W", r, c, bel)
            keys = {pk}
            for tt in dev.tiles_at.get((r, c), ()):
                if not tt.startswith("SYSIO"):
                    continue
                for fam in (dev.family, "LIFCL"):
                    pips, conns = dev.tiletype(tt, fam)
                    src = [fw for to, fw, bits in pips + conns
                           if to == bel and "JCIBMUXOUT" in fw]
                    if src:
                        routing.extra[pk] |= {wire_key(dev, r, c, tt, fw) for fw in src}
                        break
            return keys
        else:
            keys = set()
            for tt in dev.tiles_at.get((cr, cc), ()):
                pips, conns = dev.tiletype(tt)
                keys |= {("W", cr, cc, to) for to, fw, bits in pips + conns
                         if to.endswith("_CIBTEST") and fw.startswith("JCIBMUXOUT")}
        for k in keys:
            io_alias[k] = "R{}C{}_{}".format(r, c, bel)
        return keys
    return set()


def slice_pin_names(pin):
    """{routing node name: slice letter} for an SDF SLICE pin in each of the 4 slices."""
    return {SLICE_PIN_WIRES.get(pin, "J{p}_SLICE{s}").format(p=pin, s=s): s for s in "ABCD"}


def place_from_routing(dev, routing, arcs, site):
    """Place SLICE cells that no timing report names: trace back from a placed sink pin until a
    source slice pin of the right name is reached; its location is the source cell's site.
    Repeated until nothing changes, so whole trees of LUTs feeding a placed cell get placed."""
    while True:
        changed = False
        for src, dst in arcs:
            if src[0] in site or dst[0] not in site:
                continue
            names = slice_pin_names(src[1])
            for dk in sorted(pin_keys(dev, site[dst[0]], dst[1], routing, {})):
                path_ = routing.trace(dk, lambda k: k[0] == "W" and k[3] in names)
                if path_:
                    k = path_[0][0]
                    site[src[0]] = "SLICE_R{}C{}{}".format(k[1], k[2], names[k[3]])
                    changed = True
                    break
        if not changed:
            return


# ---------------------------------------------------------------------------------------------

def main():
    fasm, vo, sdf_fn, pad, out = sys.argv[1:6]
    twrs = sys.argv[6:]
    dev = Device(FAMILY, DEVICE)
    routing = Routing(dev, fasm)
    member2cell, cell2ports = parse_vo(vo)
    site = parse_twr(twrs, member2cell)
    port2site, pin2site = parse_pad(pad)
    # IO cells: placement from the .pad file, by top-level port (or by package pin from the twr)
    for cell, ports in cell2ports.items():
        for p in ports:
            if p in port2site:
                site[cell] = port2site[p]
    for cell, s in list(site.items()):
        m = re.match(r'^(?:SEIO|DIFFIO)\w*?_CORE_(\w+)$', s)
        if m and m.group(1) in pin2site:
            site[cell] = pin2site[m.group(1)]

    sdf = parse_sdf_file(sdf_fn).cells["top"]
    arcs = [(tuple(unescape(x) for x in f.rsplit("/", 1)), tuple(unescape(x) for x in t.rsplit("/", 1)))
            for f, t in sorted(sdf.interconnect.keys())]
    n_report = len(site)
    place_from_routing(dev, routing, arcs, site)
    print("placement: {} cells from timing reports and .pad, {} more from the routing".format(
        n_report, len(site) - n_report))
    arc2pips, wire_fanout = {}, defaultdict(int)
    io_alias = {}
    stats = defaultdict(int)
    failures = []
    for src, dst in arcs:
        if src[0] not in site or dst[0] not in site:
            stats["unplaced"] += 1
            failures.append(("unplaced", src, dst, site.get(src[0]), site.get(dst[0])))
            continue
        skeys = pin_keys(dev, site[src[0]], src[1], routing, io_alias)
        dkeys = pin_keys(dev, site[dst[0]], dst[1], routing, io_alias)
        path_ = None
        for dk in sorted(dkeys):
            path_ = routing.trace(dk, skeys)
            if path_ is not None:
                break
        if path_ is None:
            stats["untraced"] += 1
            failures.append(("untraced", src, dst, site[src[0]], site[dst[0]]))
            continue
        stats["traced"] += 1
        stats["via_edge_alias"] += any(p in routing.alias for p in path_)
        stats["via_ref"] += any(p in routing.ref_edges for p in path_)
        # an alias pair (a, b) is one node under two names: drop it and call b by a's name
        rename = {}
        for a, b in path_:
            if (a, b) in routing.alias:
                rename[b] = rename.get(a, a)
        pips = [(key_name(dev, rename.get(a, a), io_alias), key_name(dev, rename.get(b, b), io_alias))
                for a, b in path_ if (a, b) not in routing.alias]
        arc2pips[src, dst] = pips
        for a, b in pips:
            wire_fanout[a] += 1
    with open(out, "wb") as pf:
        pickle.dump(dict(arc2pips=arc2pips, wire_fanout=dict(wire_fanout)), pf)
    total = stats["traced"] + stats["unplaced"] + stats["untraced"]
    print("{} interconnect arcs: {} traced, {} unplaced, {} untraced".format(
        total, stats["traced"], stats["unplaced"], stats["untraced"]))
    print("  ({} of the traced arcs use a wire alias (edge turn-round or CIBTEST input), {} a {} arc "
          "of a tile type LFCPNX has no routing for)".format(stats["via_edge_alias"], stats["via_ref"],
                                                           Device.REF_FAMILY))
    with open(out + ".failures.txt", "w") as ff:
        for f in failures:
            ff.write(" ".join(str(x) for x in f) + "\n")


if __name__ == "__main__":
    main()
