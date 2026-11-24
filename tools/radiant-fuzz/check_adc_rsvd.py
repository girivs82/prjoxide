#!/usr/bin/env python3
"""
Check that R69C158 JCIBMUXOUTC0 / C1 carry the net Radiant ties the ADC's RSVDH / RSVDL to, in the
Radiant-routed designs of timing/fuzzers/LFCPNX/15-adc-pins. RSVDH and RSVDL are tied to one constant
net (GND_net in the backannotated netlist, from a constant LUT that the timing report does not place),
so per design: trace each wire backward through the routing to the start of its route and check that
both reach the same start, and that it is the start of no other ADC input's route.

Usage (in the container, PYTHONPATH as for infer_adc_conns.py): check_adc_rsvd.py <design dir>
"""
import glob
import re
import sys
from os import path

import extract_route_cram as E

d = sys.argv[1]
dev = E.Device(E.FAMILY, E.DEVICE)
# the database's ADC input wires (relative to the ADC tile R68C159), and the two to check
OTHERS = {"ADCEN": (68, 158, "JCIBMUXOUTA0"), "SOC": (68, 158, "JCIBMUXOUTA5"), "CAL": (69, 158, "JCIBMUXOUTB0"),
          "CHAEN": (69, 158, "JCIBMUXOUTB5"), "CHBEN": (69, 158, "JCIBMUXOUTB4"), "CONVSTOP": (69, 158, "JCIBMUXOUTB3"),
          "RESETN": (69, 158, "JCIBMUXOUTC4")}
OTHERS.update({"CHASEL%d" % k: (69, 158, "JCIBMUXOUTA%d" % k) for k in range(4)})
OTHERS.update({"CHBSEL%d" % k: (69, 158, "JCIBMUXOUTA%d" % (k + 4)) for k in range(4)})
CHECK = {"C0": (69, 158, "JCIBMUXOUTC0"), "C1": (69, 158, "JCIBMUXOUTC1")}


def roots(routing, k):
    seen, fr, out = {k}, [k], set()
    while fr:
        nx = []
        for x in fr:
            ds = routing.drivers(x)
            if not ds:
                out.add(x)
            for s_ in ds:
                if s_ not in seen:
                    seen.add(s_)
                    nx.append(s_)
        fr = nx
        if len(seen) > 20000:
            break
    return out


same = n = excl = 0
for fasm in sorted(glob.glob(path.join(d, "work", "design_*.fasm"))):
    routing = E.Routing(dev, fasm)
    r = {k: roots(routing, ("W",) + v) for k, v in CHECK.items()}
    o = set()
    for p, v in OTHERS.items():
        o |= roots(routing, ("W",) + v)
    n += 1
    common = r["C0"] & r["C1"]
    same += bool(common)
    excl += bool(common) and not (common & o)
    print(fasm.split("/")[-1], "C0 / C1 share a route start:", bool(common), "shared with another ADC input:", bool(common & o))
print("designs", n, "C0 and C1 on one net:", same, "and that net feeds no other ADC input:", excl)
