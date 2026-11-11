#!/usr/bin/env python3
"""
Compare fuzzed LFCPNX tile types with LIFCL tiles of the same name (enums and words).
SKALP currently uses LIFCL copies for many LFCPNX tiles; this shows where that is right.

Usage: compare_with_lifcl.py <db root> TILETYPE_GLOB...   e.g. 'SYSIO_*' 'EBR_*'
"""
import fnmatch
import os
import re
import sys

ENTRY = re.compile(r'"([^"]+)": \(')
BIT = re.compile(r"\(frame:(\d+),bit:(\d+),invert:(true|false),\)")


def settings(path):
    text = open(path).read()
    if "enums:" not in text:
        return {}
    body = text.split("enums:", 1)[1].split("conns:", 1)[0]
    out = {}
    marks = list(ENTRY.finditer(body))
    for i, m in enumerate(marks):
        seg = body[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(body)]
        if "options:" not in seg:
            continue  # option entries themselves are matched too; keep enum level only
        opts = {}
        for o in re.finditer(r'"([^"]+)": \[([^\]]*)\]', seg):
            opts[o.group(1)] = frozenset(BIT.findall(o.group(2)))
        out[m.group(1)] = opts
    return out


def main():
    root, pats = sys.argv[1], sys.argv[2:]
    lf = os.path.join(root, "LFCPNX", "tiletypes")
    li = os.path.join(root, "LIFCL", "tiletypes")
    for f in sorted(os.listdir(lf)):
        t = f[:-4]
        if not any(fnmatch.fnmatch(t, p) for p in pats):
            continue
        a = settings(os.path.join(lf, f))
        if not a:
            continue
        lp = os.path.join(li, f)
        if not os.path.exists(lp):
            print("{}: {} enums, no LIFCL tile of that name".format(t, len(a)))
            continue
        b = settings(lp)
        same = [k for k in a if b.get(k) == a[k]]
        diff = [k for k in a if k in b and b[k] != a[k]]
        only = [k for k in a if k not in b]
        print("{}: {} identical, {} different, {} LFCPNX-only, {} LIFCL-only".format(
            t, len(same), len(diff), len(only), len([k for k in b if k not in a])))
        for k in diff:
            for o in sorted(set(a[k]) | set(b[k])):
                if a[k].get(o) != b[k].get(o):
                    print("   {} = {}: LFCPNX {} LIFCL {}".format(k, o, sorted(a[k].get(o, [])), sorted(b[k].get(o, []))))


if __name__ == "__main__":
    main()
