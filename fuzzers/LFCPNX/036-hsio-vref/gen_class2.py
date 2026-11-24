"""
Generate the class-II output designs for DRIVE_1V5 / DRIVE_1V35 "10" (see write_class2_drive.py and
README.md, "SSTL15_II / SSTL135_II drive"): one output of the given IO type on a pad of every bank
3 / 4 / 5 SYSIO tile type, each driven by its own register. Built with the radiant.sh CLI flow
(LSE, map, par, bitgen) and decoded with prjoxide unpack.

A pad PB<n>A is in the tile at column n (PIOA, first-tile types SYSIO_B<k>_0*), PB<n>B in the tile at
column n + 1 (PIOB, second-tile types SYSIO_B<k>_1*).

Usage: gen_class2.py <ball list> <IO type> <out basename>
  ball list: lines "PB<n><A|B> <ball>/<bank>" (the package pin list)
"""
import json
import os
import re
import sys

import database

AVOID = {"R4", "R5", "M9"}   # the clock, data and output pins of the design


def pads(ball_list):
    grid = json.load(open(os.path.join(database.get_db_root(), "LFCPNX", "LFCPNX-100", "tilegrid.json")))["tiles"]
    balls = {}
    for line in open(ball_list):
        p = line.split()
        if len(p) == 2 and "/" in p[1]:
            balls[p[0]] = p[1].split("/")[0]
    types = {}
    for n in grid:
        m = re.match(r'CIB_R74C(\d+):(SYSIO_B[345]_\S+)$', n)
        if m:
            types.setdefault(m.group(2), []).append(int(m.group(1)))
    sel, used = [], set()
    for tt, cols in sorted(types.items()):
        first = bool(re.match(r'SYSIO_B\d_0', tt))
        for c in sorted(cols):
            pad = "PB{}{}".format(c, "A") if first else "PB{}{}".format(c - 1, "B")
            if pad in balls and balls[pad] not in AVOID and balls[pad] not in used:
                sel.append((tt, pad, balls[pad]))
                used.add(balls[pad])
                break
        else:
            raise SystemExit("no pad for " + tt)
    return sel


def main():
    ball_list, io, base = sys.argv[1:4]
    sel = pads(ball_list)
    n = len(sel)
    v = ["module top(input clk, input d, output reg q, output [{}:0] o);".format(n - 1),
         "    reg [{}:0] r; always @(posedge clk) r <= {{r[{}:0], d}};".format(n, n - 1),
         "    assign o = r[{}:0];".format(n - 1),
         "    always @(posedge clk) q <= r[{}];".format(n),
         "endmodule"]
    p = ["ldc_set_location -site {R4} [get_ports clk]", "ldc_set_location -site {R5} [get_ports d]",
         "ldc_set_location -site {M9} [get_ports q]"]
    p += ["ldc_set_port -iobuf {{IO_TYPE=LVCMOS33}} [get_ports {}]".format(x) for x in ("clk", "d", "q")]
    for i, (tt, pad, ball) in enumerate(sel):
        p.append("ldc_set_location -site {{{}}} [get_ports {{o[{}]}}]".format(ball, i))
        p.append("ldc_set_port -iobuf {{IO_TYPE={}}} [get_ports {{o[{}]}}]".format(io, i))
    open(base + ".v", "w").write("\n".join(v) + "\n")
    open(base + ".pdc", "w").write("\n".join(p) + "\n")
    open(base + ".sdc", "w").write("create_clock -name clk -period 10 [get_ports clk]\n")
    for tt, pad, ball in sel:
        print(tt, pad, ball)


if __name__ == "__main__":
    main()
