#!/usr/bin/env python3
"""For every attribute build: FASM of its PCSX1 attribute values on IP_PCS_LANE0, pack with prjoxide,
compare with Radiant's lane-0 bytes. Bytes Radiant omits are at their default; count those too."""
import json, os, re, subprocess, sys
P = os.path.expanduser("~/src/radiant-work/target-host/release/prjoxide")
DB = os.path.expanduser("~/src/prjoxide/database")
ron = open(os.path.join(DB, "LFCPNX/iptypes/PCS_LANE.ron")).read()
words = set(re.findall(r'\n    "([A-Z0-9_]+)": \(\n      bits:', ron)); enums = set(re.findall(r'\n    "([A-Z0-9_]+)": \(\n      options:', ron))
def ip(f):
    d = {}
    for l in open(f):
        if l.startswith("IP_UNKNOWN.0x0E42"): d[int(l[13:21], 16) & 0xFFFF] = int(l.split("8'h")[1][:2], 16)
    return d
names = sys.argv[1:]
tot_ok = tot = 0; bad_builds = []
for n in names:
    if not os.path.exists("%s/b/%s.bit" % (n, n)): continue
    if not os.path.exists("%s.fasm" % n):
        subprocess.run([P, "unpack", "--db", DB, "%s/b/%s.bit" % (n, n), "%s.fasm" % n], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    s = open("%s/b/%s.v" % (n, n)).read()
    bv = {m.group(1): m.group(2) for m in re.finditer(r'defparam \\PCSX1_inst\.u_PCSX1 \.([A-Z0-9_]+) = "(.*?)";', s)}
    L = ['{ oxide.device="LFCPNX-100" }', '{ oxide.device_variant="" }', '']
    for a in sorted(words):
        v = bv[a][2:]; L.append("IP_PCS_LANE0.%s[%d:0] = %d'b%s" % (a, len(v) - 1, len(v), v))
    for a in sorted(enums): L.append("IP_PCS_LANE0.%s.%s" % (a, bv[a]))
    open("/tmp/pt.fasm", "w").write("\n".join(L) + "\n")
    subprocess.run([P, "pack", "--db", DB, "/tmp/pt.fasm", "/tmp/pt.bit"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([P, "unpack", "--db", DB, "/tmp/pt.bit", "/tmp/pt_dec.fasm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    R = ip("%s.fasm" % n); Q = ip("/tmp/pt_dec.fasm")
    bad = [o for o in R if Q.get(o) != R[o]]
    tot += len(R); tot_ok += len(R) - len(bad)
    if bad: bad_builds.append((n, len(bad), [(hex(o), hex(R[o]), hex(Q.get(o, -1))) for o in sorted(bad)[:4]]))
print("builds:", len(names), "| Radiant-written lane-0 bytes reproduced:", tot_ok, "of", tot)
for b in bad_builds[:15]: print("  ", b)
