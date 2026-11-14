#!/usr/bin/env python3
"""Wrap ipgen output <name>/rtl/<name>.v in a top with every input driven from one register
(reference-clock inputs, which only accept dedicated sources, left unconnected) and every output
XOR-reduced into one register."""
import re, sys
name = sys.argv[1]
src = open("%s/rtl/%s.v" % (name, name)).read()
m0 = re.search(r'module\s+%s\s*\(' % name, src)
body = src[m0.start():src.index('endmodule', m0.start())]
ports = []
for m in re.finditer(r'^\s*(input|output|inout)\s+(?:wire\s+|reg\s+)?(\[[^\]]+\])?\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*;', body, re.M):
    for n in m.group(3).split(','):
        ports.append((m.group(1), m.group(2) or '', n.strip()))
def width(w):
    if not w: return 1
    a, b = [int(x) for x in re.findall(r'\d+', w)][:2]
    return abs(a - b) + 1
L = ["module top(input clk, input d, output reg q);", "  reg dr; always @(posedge clk) dr <= d;"]
conns = []
for dirn, w, n in ports:
    if dirn == 'input':
        conns.append(".%s()" % n if re.search(r'refclk|diffioclk', n, re.I) else ".%s({%d{dr}})" % (n, width(w)))
    else:
        L.append("  wire %s o_%s;" % (w, n)); conns.append(".%s(o_%s)" % (n, n))
outs = [n for d_, w, n in ports if d_ == 'output']
L.append("  %s u_mpcs (%s);" % (name, ",\n    ".join(conns)))
L.append("  always @(posedge clk) q <= ^{%s};" % ", ".join("o_" + n for n in outs))
L.append("endmodule")
open("%s/%s_top.v" % (name, name), "w").write("\n".join(L) + "\n" + src)
