#!/usr/bin/env python3
"""Data-path trace of the unpacked scope netlist: do the left-edge and right-edge
ADC (IDDRC) front-ends feed two independent logic clusters (scope + DMM), or one
integrated design?

Method: build a dataflow graph (routing assigns + bel input->output edges),
EXCLUDING high-fanout global nets (clocks/resets/enables/constants) so the trace
follows real data, not the clock tree. Forward-BFS from the left-edge ADC inputs
and from the right-edge ADC inputs; compare the two reachable sets and which
BRAMs / output pins each reaches.
"""
import os, re
from collections import defaultdict, deque, Counter

NET = os.path.expanduser("~/m5/scope_unpacked2.v")
if not os.path.exists(NET):
    NET = os.path.expanduser("~/m5/scope_unpacked.v")
txt = open(NET).read()
CONST = {"VCC", "VSS", "GND", "VDD"}
norm = lambda w: w[1:] if w.startswith("`") else w

# --- routing edges (src -> dst) from assigns ---
edges = defaultdict(set)
fanout = Counter()
for dst, src in re.findall(r"^assign\s+(\S+)\s*=\s*(\S+?);", txt, re.M):
    s, d = norm(src), norm(dst)
    if s in CONST or d in CONST:
        continue
    edges[s].add(d)
    fanout[s] += 1

# --- bel input->output edges; collect cell locations ---
insts = re.findall(r"^([A-Z][A-Z0-9_]*)\s+(\S+)\s*\((.*?)\);", txt, re.S | re.M)
def ports(body): return {k: norm(v) for k, v in re.findall(r"\.(\w+)\(([^)]*)\)", body)}
loc_re = re.compile(r"R(\d+)C(\d+)")

iddrc_left, iddrc_right = [], []   # output wires of edge ADC cells
bram_in, bram_out = {}, {}          # name -> sets of wires
obuf_pins = []                      # (wire feeding OBUF, name)
for typ, name, body in insts:
    p = ports(body)
    m = loc_re.search(name)
    col = int(m.group(2)) if m else -1
    if typ in ("IDDRC", "IDDR", "IDES", "IDDRCS"):
        outs = [v for k, v in p.items() if k.startswith("Q") and v and v not in CONST]
        if col == 1:    iddrc_left += outs
        elif col == 20: iddrc_right += outs
    elif typ == "LUT4":
        ins = [p[k] for k in ("I0","I1","I2","I3") if p.get(k) and p[k] not in CONST]
        if p.get("F"):
            for i in ins: edges[i].add(p["F"]); fanout[i]+=1
    elif typ.startswith("ALU"):
        outs=[v for k,v in p.items() if k in ("SUM","COUT","F") and v not in CONST]
        ins=[v for k,v in p.items() if k in ("I0","I1","I3","CIN") and v and v not in CONST]
        for i in ins:
            for o in outs: edges[i].add(o); fanout[i]+=1
    elif typ.startswith("DFF"):     # register: D -> Q (sequential boundary, still dataflow)
        if p.get("D") and p.get("Q") and p["D"] not in CONST:
            edges[p["D"]].add(p["Q"]); fanout[p["D"]]+=1
    elif typ.startswith("BSRAM"):
        bram_in[name] = {v for k,v in p.items() if (k.startswith("DI") or k.startswith("AD")) and v not in CONST}
        bram_out[name] = {v for k,v in p.items() if k.startswith("DO") and v not in CONST}
        for i in bram_in[name]:
            for o in bram_out[name]: edges[i].add(o); fanout[i]+=1
    elif typ in ("OBUF","IOBUF","TBUF"):
        if p.get("I") and p["I"] not in CONST:
            obuf_pins.append((p["I"], name))

# --- exclude high-fanout global nets (clock/reset/enable/const distribution) ---
FANOUT_CAP = 24
globals_ = {n for n, f in fanout.items() if f > FANOUT_CAP}
print(f"graph: {len(edges)} source nets; excluding {len(globals_)} high-fanout (> {FANOUT_CAP}) global nets")

def bfs(starts):
    seen = set(s for s in starts if s)
    q = deque(seen)
    while q:
        n = q.popleft()
        if n in globals_:
            continue
        for nx in edges.get(n, ()):
            if nx not in seen:
                seen.add(nx); q.append(nx)
    return seen

print(f"\nADC front-ends: {len(iddrc_left)} left-edge IDDRC outputs, "
      f"{len(iddrc_right)} right-edge IDDRC outputs")
L = bfs(iddrc_left)
R = bfs(iddrc_right)
both = L & R
print(f"\nreachable from LEFT  ADC: {len(L)} nets")
print(f"reachable from RIGHT ADC: {len(R)} nets")
print(f"overlap (in both): {len(both)}  "
      f"({100*len(both)/max(1,min(len(L),len(R))):.0f}% of the smaller set)")

def which(reach, anchors, label):
    hit = [n for n, wires in anchors.items() if wires & reach]
    print(f"  {label}: {hit}")
print("\nBRAMs reached:")
which(L, bram_in, "  from LEFT  -> BRAM inputs")
which(R, bram_in, "  from RIGHT -> BRAM inputs")

# --- backward trace from each BRAM to map all acquisition channels ---
rev = defaultdict(set)
for s, ds in edges.items():
    for d in ds:
        rev[d].add(s)
def bfs_back(starts):
    seen = set(s for s in starts if s)
    q = deque(seen)
    while q:
        n = q.popleft()
        if n in globals_: continue
        for p in rev.get(n, ()):
            if p not in seen:
                seen.add(p); q.append(p)
    return seen

# locate IDDRC source cells per net for labeling
iddrc_all = set(iddrc_left) | set(iddrc_right)
print("\n=== backward trace from each BRAM (what feeds it) ===")
chans = {}
for nm in sorted(bram_in):
    back = bfs_back(bram_in[nm])
    adc_l = len(back & set(iddrc_left)); adc_r = len(back & set(iddrc_right))
    chans[nm] = back
    print(f"  {nm}: {len(back)} source nets; ADC inputs in cone: left={adc_l} right={adc_r}")
# pairwise overlap of the 4 BRAM source cones
print("\n=== pairwise overlap of BRAM source cones (are the 4 channels independent?) ===")
names = sorted(chans)
for i in range(len(names)):
    for j in range(i+1, len(names)):
        ov = len(chans[names[i]] & chans[names[j]])
        print(f"  {names[i]} vs {names[j]}: shared nets = {ov}")
