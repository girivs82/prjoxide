"""LFG672 clock-capable pads (PCLKT* or *_GPLL*_IN, true side, banks 1-7) as "<pin> <bank>" lines."""
import json, re, sys
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "../../../database/LFCPNX/LFCPNX-100/iodb.json"))
pk = d["packages"].index("LFG672")
for p in d["pads"]:
    if p["bank"] != 0 and p["name"].endswith("A") and any(re.match(r"PCLKT|.*GPLL.*_IN", f) for f in p["func"]):
        print(p["pins"][pk], p["bank"])
