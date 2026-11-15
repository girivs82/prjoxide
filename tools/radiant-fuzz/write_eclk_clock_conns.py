#!/usr/bin/env python3
"""
Write the LFCPNX HP-bank edge-clock connections that come from Radiant's clock pips rather than from
SDF arcs (see fuzzers/LFCPNX/154-ddrll/README.md, "Edge-clock connections"):

- bank 4 (BMID_0_ECLK_1), k = 0-3, as banks 3 / 5 already have them:
  N1:JECLKIN_ECLKSYNC_CORE_ECLKSYNC4_k <- G:JMUXINk_ECLKBANK_CORE_ECLKBANK4
  N1:JECLKOUT_ECLKSYNC_CORE_ECLKSYNC4_k <- N1:JECLKIN_ECLKSYNC_CORE_ECLKSYNC4_k
  N1:JECLKSYNCMk_ECLKCASMUX_CORE_ECLKCASMUX4 <- N1:JECLKOUT_ECLKSYNC_CORE_ECLKSYNC4_k
  N1:JECLKIN_ECLKDIV_CORE_ECLKDIVB4_k <- G:JECLKOUTk_ECLKCASMUX_CORE_ECLKCASMUX4
  (check_eclk_routing.py on timing/fuzzers/LFCPNX/18-eclk-pins: with every ECLKSYNC pinned, each PCLK
  ball maps to one JPCLKT input in all designs only if ECLKSYNC k takes JMUXIN k; ECLKSYNC k always
  drives CASMUX output k through SYNCM k; par accepts ECLKDIV k only on edge clock k.)
- the left DDRDLL's edge-clock feed: ECLK_0 G:JCLKOUT_ECLKDDRL_k <- N1:JECLKTREE1_ECLKDDRL_k (bank 4's
  CASMUX output k), replacing LIFCL's <- N1:JECLKTREE0_ECLKDDRL_k (bank 5's): with the DDRDLL on the
  left and the only edge-clock user, Radiant cascades even a bank-5 ECLKSYNC into CASMUX4, never 5.
- DOSCL_P18 JECLKk_I0 <- G:JCLKOUT_ECLKDDRL_k (the left DDRDLL's CLKIN mux inputs; edge clock k sets
  the mux pip from JECLKk_I0, 154-ddrll).
- SYSIO_B5_1_DQS0: the DQSBUF edge-clock inputs N1W5:JECLKk_I_DQS_TOP_ECLK_ROUTING_MUX come from
  ECLKCASMUX5, not ECLKCASMUX4 (copied from bank 4): a bank-5 DQSBUF clocked from a bank-5 ECLKSYNC,
  with the DDRDLL on the right, uses CASMUX5 only.

Usage: write_eclk_clock_conns.py [database root]
"""
import os
import re
import sys
from collections import defaultdict

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                                            "database")
TT = os.path.join(root, "LFCPNX", "tiletypes")


def load_conns(t):
    ci = t.index("\n  conns: {")
    ce = t.index("\n  },\n", ci) + len("\n  },\n")
    have = defaultdict(list)
    for to, body in re.findall(r'\n    "([^"]+)": \[(.*?)\n    \],', t[ci:ce], re.S):
        have[to] += re.findall(r'from_wire: "([^"]+)"', body)
    return (t[:ci], t[ce:]), have        # the tail (always_on, closing parenthesis) is kept


def store(tt, head, have):
    pre, tail = head
    body = "".join('    "{}": [\n{}    ],\n'.format(
        to, "".join('      (\n        from_wire: "{}",\n      ),\n'.format(fw) for fw in sorted(fws)))
        for to, fws in sorted(have.items()))
    open(os.path.join(TT, tt + ".ron"), "w").write(pre + "\n  conns: {\n" + body + "  },\n" + tail)


def edit(tt, add=(), replace=()):
    t = open(os.path.join(TT, tt + ".ron")).read()
    if "\n  conns: {}," in t:
        t = t.replace("\n  conns: {},", "\n  conns: {\n  },", 1)
    head, have = load_conns(t)
    n = 0
    for to, old, new in replace:
        if old in have.get(to, []):
            have[to] = [new if f == old else f for f in have[to]]
            n += 1
        elif new not in have.get(to, []):
            raise SystemExit("{}: {} has neither {} nor {}".format(tt, to, old, new))
    for to, frm in add:
        if frm not in have[to]:
            have[to].append(frm)
            n += 1
    store(tt, head, have)
    print("{}: {} connections added or replaced".format(tt, n))


def main():
    b4 = []
    for k in range(4):
        b4 += [("N1:JECLKIN_ECLKSYNC_CORE_ECLKSYNC4_%d" % k, "G:JMUXIN%d_ECLKBANK_CORE_ECLKBANK4" % k),
               ("N1:JECLKOUT_ECLKSYNC_CORE_ECLKSYNC4_%d" % k, "N1:JECLKIN_ECLKSYNC_CORE_ECLKSYNC4_%d" % k),
               ("N1:JECLKSYNCM%d_ECLKCASMUX_CORE_ECLKCASMUX4" % k, "N1:JECLKOUT_ECLKSYNC_CORE_ECLKSYNC4_%d" % k),
               ("N1:JECLKIN_ECLKDIV_CORE_ECLKDIVB4_%d" % k, "G:JECLKOUT%d_ECLKCASMUX_CORE_ECLKCASMUX4" % k)]
    edit("BMID_0_ECLK_1", add=b4)
    edit("ECLK_0", replace=[("G:JCLKOUT_ECLKDDRL_%d" % k, "N1:JECLKTREE0_ECLKDDRL_%d" % k,
                             "N1:JECLKTREE1_ECLKDDRL_%d" % k) for k in range(4)])
    edit("DOSCL_P18", add=[("JECLK%d_I0" % k, "G:JCLKOUT_ECLKDDRL_%d" % k) for k in range(4)])
    edit("SYSIO_B5_1_DQS0", replace=[("N1W5:JECLK%d_I_DQS_TOP_ECLK_ROUTING_MUX" % k,
                                      "G:JECLKOUT%d_ECLKCASMUX_CORE_ECLKCASMUX4" % k,
                                      "G:JECLKOUT%d_ECLKCASMUX_CORE_ECLKCASMUX5" % k) for k in range(4)])


if __name__ == "__main__":
    main()
