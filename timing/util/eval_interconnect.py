"""Model error of interconnect_<grade>.json files on the routed designs' SDF arcs (as solve_interconnect
builds them). Usage: eval_interconnect.py <output dir> <grade> <json>... [--only REGEX]"""
import glob, json, math, pickle, re, sys
from os import path
import solve_interconnect as S
from timing_config import zero_delay_classes

folder, grade = sys.argv[1], sys.argv[2]
jsons = [a for a in sys.argv[3:] if a.endswith(".json")]
only = re.compile(sys.argv[sys.argv.index("--only") + 1]) if "--only" in sys.argv else None
# --cls REGEX: only arcs with a pip of a matching class
cls_re = re.compile(sys.argv[sys.argv.index("--cls") + 1]) if "--cls" in sys.argv else None
models = [json.load(open(j))["pip_classes"] for j in jsons]
stats = [dict(n=0, se=0.0, mx=-1e9, mn=1e9, miss=0) for _ in models]
for pf in sorted(glob.glob(path.join(folder, "*_route.pickle"))):
    d = pf.replace("_route.pickle", "")
    if only and not only.search(path.basename(d)):
        continue
    sp = "{}_{}.sdf.pickle".format(d, grade)
    if not path.exists(sp):
        continue
    a2p = pickle.load(open(pf, "rb"))["arc2pips"]
    sdf = pickle.load(open(sp, "rb")).cells["top"]
    for (f, t), dly in sdf.interconnect.items():
        src, dst = S.conv_sdf_port(f), S.conv_sdf_port(t)
        if (src, dst) not in a2p:
            continue
        cls = [S.get_pip_class(p) for p in a2p[src, dst]]
        if None in cls:
            continue
        if cls_re and not any(cls_re.search(c) for c in cls):
            continue
        meas = max(dly.rising.maxv, dly.falling.maxv)
        for m, st in zip(models, stats):
            tot, miss = 0, False
            for c in cls:
                if c in zero_delay_classes:
                    continue
                if c not in m:
                    miss = True
                    continue
                tot += m[c]["base"][1]
            st["miss"] += miss
            e = tot - meas
            st.setdefault("sum", 0.0)
            st["sum"] += e
            st["n"] += 1; st["se"] += e * e; st["mx"] = max(st["mx"], e); st["mn"] = min(st["mn"], e)
for j, st in zip(jsons, stats):
    print("{}: arcs {} rms {:.1f} ps, mean {:.1f}, min {:.0f}, max {:.0f}, arcs with an unknown class {}".format(
        j, st["n"], math.sqrt(st["se"] / max(st["n"], 1)), st.get("sum", 0) / max(st["n"], 1), st["mn"], st["mx"], st["miss"]))
