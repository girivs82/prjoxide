# LFCPNX: fabric-generated clocks (a register output) driving many registers, so Radiant puts them
# on the global clock network through the mid muxes' fabric entries (PCLKCIB -> HPF/VPF mid), and
# high-fanout fabric control signals (LSR / CE of many registers; Radiant keeps these on general
# routing). Each clock's source register is pinned (ldc_set_location) next to one of the four mid
# muxes in turn, so the clocks enter the global network at different sides (the PCLKCIB entries of
# the top / bottom / left / right mid muxes). For the jpclkcib* ->
# j{h,v}pf_mid / *_mid_entry classes.
#
# Usage: gen_fabclk.py <basename>   (writes <basename>.v and <basename>.pdc)
import json
import os
import random
import re
import sys

base = sys.argv[1]
grid = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..",
                                   "database", "LFCPNX", "LFCPNX-100", "tilegrid.json")))
grid = grid.get("tiles", grid)
plc = [tuple(map(int, re.match(r'R(\d+)C(\d+):PLC$', n).groups())) for n in grid if re.match(r'R\d+C\d+:PLC$', n)]
maxr, maxc = max(r for r, c in plc), max(c for r, c in plc)
# A fabric signal reaches the global network only through the PCLKCIB entries of the four mid muxes
# (LMID R37C0, RMID R37C159, TMID R0C73, BMID R74C73), each fed from one CIBMUXOUT wire of a nearby
# CIB (the MID tile types' connections, e.g. RMID PCLKCIBR4 <- N18W13:JCIBMUXOUTD7, i.e. R19C146).
# par refuses a fabric clock whose source register is not next to an entry ("routed with generic
# routing resources"), so each clock's source is pinned to the PLC tile of one entry's CIB (outer-
# most PLC row / column for the entries in the IO ring's CIBs), slice C / D (in test builds par
# refused some sources in A / B). Design N takes entries 4N .. 4N+3 of the 30 in turn, so eight
# designs cover every entry.
MIDS = {"R": (37, 159), "L": (37, 0), "T": (0, 73), "B": (74, 73)}
ENTRY_SRC = {   # entry -> (side, row offset, column offset) of its CIB from the MID tile
    "R0": (-2, -1), "R1": (-1, -1), "R2": (1, -1), "R3": (2, -1), "R4": (-18, -13), "R5": (-9, -13),
    "R6": (9, -13), "R7": (18, -13), "R8": (-9, -13),
    "L0": (-2, 1), "L1": (-1, 1), "L2": (1, 1), "L3": (2, 1), "L4": (-18, 13), "L5": (-9, 13),
    "L6": (9, 13), "L7": (18, 13), "L8": (-9, 13),
    "T0": (1, -1), "T1": (1, -1), "T2": (1, 0), "T3": (1, 1), "T4": (1, 2), "T5": (1, 3),
    "B0": (-1, -2), "B1": (-1, -1), "B2": (-1, 0), "B3": (-1, 1), "B4": (-1, 2), "B5": (-1, 3),
}
minr, minc = min(r for r, c in plc), min(c for r, c in plc)


plc_set = set(plc)


def src_tile(entry):
    mr, mc = MIDS[entry[0]]
    dr, dc = ENTRY_SRC[entry]
    r, c = min(max(mr + dr, minr), maxr), min(max(mc + dc, minc), maxc)
    # the far entries' CIBs (rows 19 / 28 / 46 / 55) are in CIB-only rows with no slices: take
    # the logic tile just above (or below) instead
    for d in (0, -1, 1, -2, 2):
        if (r + d, c) in plc_set:
            return r + d, c
    return r, c


ENTRIES = sorted(ENTRY_SRC)
dnum = int(re.search(r'(\d+)$', base).group(1)) if re.search(r'(\d+)$', base) else random.randint(0, 7)
out = open(base + ".v", "w")
_print = print


def print(*a):
    _print(*a, file=out)

# one clock per side (par refuses some placements when two sources compete for a side's entries)
NCLK = int(os.environ.get("NCLK", "4"))
FAN = int(os.environ.get("FAN", "48"))
NCTL = int(os.environ.get("NCTL", "4"))

print("module top(input clk, input [7:0] d, output q);")
body, cap = [], []
# divider registers: gc[i] toggles when a free-running counter bit is set, so each is its own net
print("    reg [15:0] cnt;")
print("    always @(posedge clk) cnt <= cnt + 1'b1;")
print("    reg [{}:0] gc;".format(NCLK - 1))
print("    always @(posedge clk) gc <= gc ^ {{{}}};".format(", ".join("cnt[{}]".format(random.randint(0, 15)) for _ in range(NCLK))))
for i in range(NCLK):
    print("    reg [{}:0] s{};".format(FAN - 1, i))
    # each stage XORed with an input bit, so synthesis cannot map the chain to a shift-register memory
    print("    always @(posedge gc[{}]) s{} <= {{s{}[{}:0] ^ {{{}{{d[{}]}}}}, d[{}] ^ s{}[{}]}};".format(
        i, i, i, FAN - 2, FAN - 1, (i + 1) % 8, i % 8, i, FAN - 1))
    cap.append("^s{}".format(i))
# high-fanout control signals from registers
print("    reg [{}:0] ctl;".format(NCTL - 1))
print("    always @(posedge clk) ctl <= ctl ^ {{{}}};".format(", ".join("d[{}]".format(random.randint(0, 7)) for _ in range(NCTL))))
for j in range(NCTL):
    print("    reg [{}:0] t{};".format(FAN * 2 - 1, j))
    print("    always @(posedge clk) if (ctl[{}]) t{} <= 0; else t{} <= {{t{}[{}:0] ^ {{{}{{d[{}]}}}}, d[{}]}};".format(
        j, j, j, j, FAN * 2 - 2, FAN * 2 - 1, (j + 5) % 8, (j + 3) % 8))
    cap.append("^t{}".format(j))
print("    reg qq; always @(posedge clk) qq <= {};".format(" ^ ".join(cap)))
print("    assign q = qq;")
print("endmodule")
out.close()
pdc = []
# ENTRY_LIST="R0 R1 ..." pins the sources to those entries instead (e.g. every entry of one side, so
# that par has to use the far ones as well)
pick = os.environ["ENTRY_LIST"].split() if os.environ.get("ENTRY_LIST") else \
    [ENTRIES[(dnum * NCLK + i) % len(ENTRIES)] for i in range(NCLK)]
for i in range(NCLK):
    r, c = src_tile(pick[i])
    # (slices C / D: in test builds par accepted sources there and refused some in A / B)
    pdc.append("ldc_set_location -site {{R{}C{}{}}} [get_cells {{gc_i{}.ff_inst}}]".format(r, c, random.choice("CD"), i))
# PROHIBIT="r0:r1:c0:c1 ..." keeps par from placing anything in those PLC tiles (e.g. the centre
# CMUX tiles and the other mid muxes' entry tiles, so the far entries are the only ones left)
for box in os.environ.get("PROHIBIT", "").split():
    r0, r1, c0, c1 = map(int, box.split(":"))
    for r, c in sorted(plc_set):
        if r0 <= r <= r1 and c0 <= c <= c1:
            for z in "ABCD":
                pdc.append("ldc_prohibit -site {{R{}C{}{}}}".format(r, c, z))
open(base + ".pdc", "w").write("\n".join(pdc) + "\n")
