"""Count, over route pickles, how many arcs contain each pip class and how many are dropped by the
solver for an unclassified pip. Usage: class_census.py <pickle>... [--grep REGEX]"""
import pickle, re, sys
from collections import Counter
import solve_interconnect as S
files = [a for a in sys.argv[1:] if not a.startswith("--")]
pat = re.compile(sys.argv[sys.argv.index("--grep") + 1]) if "--grep" in sys.argv else None
files = [f for f in files if not (pat and f == pat.pattern)]
cls_arcs, unclassified = Counter(), Counter()
dropped = 0
for f in files:
    a2p = pickle.load(open(f, "rb"))["arc2pips"]
    for arc, pips in a2p.items():
        cs = set()
        bad = False
        for p in pips:
            c = S.get_pip_class(p)
            if c is None:
                bad = True
                unclassified[S.get_wirename(p[0])[2] + " -> " + S.get_wirename(p[1])[2]] += 1
            else:
                cs.add(c)
        if bad:
            dropped += 1
        else:
            for c in cs:
                cls_arcs[c] += 1
print("arcs dropped (unclassified pip):", dropped)
for c, n in sorted(cls_arcs.items()):
    if not pat or pat.search(c):
        print("  {:40s} {}".format(c, n))
print("top unclassified pips:")
for p, n in unclassified.most_common(25):
    print("  {:60s} {}".format(p, n))
