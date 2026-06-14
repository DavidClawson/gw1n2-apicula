#!/usr/bin/env python3
"""Map the FPGA's external interface (the MCU/ADC/DAC 'API' surface) and tie each
I/O pin to a functional channel. Helps answer: which pins are the high-speed ADCs
(scope), the DAC (sig-gen), and the MCU control/readout bus -- and which I/O feeds
each acquisition channel's control (what firmware must drive to enable it)."""
import os, re
from collections import defaultdict, deque

NET = os.path.expanduser("~/m5/scope_unpacked2.v")
if not os.path.exists(NET):
    NET = os.path.expanduser("~/m5/scope_unpacked.v")
txt = open(NET).read()
CONST = {"VCC", "VSS", "GND", "VDD"}
norm = lambda w: w[1:] if w.startswith("`") else w

# --- dataflow graph (same as m_datapath) ---
edges = defaultdict(set)
from collections import Counter
fanout = Counter()
for dst, src in re.findall(r"^assign\s+(\S+)\s*=\s*(\S+?);", txt, re.M):
    s, d = norm(src), norm(dst)
    if s in CONST or d in CONST: continue
    edges[s].add(d); fanout[s]+=1
insts = re.findall(r"^([A-Z][A-Z0-9_]*)\s+(\S+)\s*\((.*?)\);", txt, re.S | re.M)
def ports(b): return {k: norm(v) for k,v in re.findall(r"\.(\w+)\(([^)]*)\)", b)}
loc = re.compile(r"R(\d+)C(\d+)")
io = []                # (kind, dir, name, row, col, net)
bram_in = {}
for typ, name, body in insts:
    p = ports(body); m = loc.search(name)
    r, c = (int(m.group(1)), int(m.group(2))) if m else (-1,-1)
    if typ == "LUT4":
        ins=[p[k] for k in("I0","I1","I2","I3") if p.get(k) and p[k] not in CONST]
        if p.get("F"):
            for i in ins: edges[i].add(p["F"]); fanout[i]+=1
    elif typ.startswith("ALU"):
        outs=[v for k,v in p.items() if k in("SUM","COUT","F") and v not in CONST]
        for i in [v for k,v in p.items() if k in("I0","I1","I3","CIN") and v and v not in CONST]:
            for o in outs: edges[i].add(o); fanout[i]+=1
    elif typ.startswith("DFF"):
        if p.get("D") and p.get("Q") and p["D"] not in CONST: edges[p["D"]].add(p["Q"]); fanout[p["D"]]+=1
    elif typ.startswith("BSRAM"):
        bram_in[name]={v for k,v in p.items() if (k.startswith("DI") or k.startswith("AD")) and v not in CONST}
        for i in bram_in[name]:
            for o in {v for k,v in p.items() if k.startswith("DO") and v not in CONST}: edges[i].add(o); fanout[i]+=1
    elif typ in ("IBUF",):
        if p.get("O"): io.append((typ,"in",name,r,c,p["O"]))
    elif typ in ("OBUF","TBUF"):
        if p.get("I"): io.append((typ,"out",name,r,c,p["I"]))
    elif typ=="IOBUF":
        io.append((typ,"bidir",name,r,c,p.get("O") or p.get("I")))
    elif typ in ("IDDRC","IDDR","IDES"):
        for k,v in p.items():
            if k.startswith("Q") and v and v not in CONST: io.append((typ,"in(ddr)",name,r,c,v))
    elif typ in ("ODDRC","ODDR","OSER"):
        for k,v in p.items():
            if k in("Q0","Q1","D0") and v and v not in CONST: io.append((typ,"out(ddr)",name,r,c,v))

globals_={n for n,f in fanout.items() if f>24}
rev=defaultdict(set)
for s,ds in edges.items():
    for d in ds: rev[d].add(s)
def cone_back(starts):
    seen=set(x for x in starts if x); q=deque(seen)
    while q:
        n=q.popleft()
        if n in globals_: continue
        for p_ in rev.get(n,()):
            if p_ not in seen: seen.add(p_); q.append(p_)
    return seen
def cone_fwd(starts):
    seen=set(x for x in starts if x); q=deque(seen)
    while q:
        n=q.popleft()
        if n in globals_: continue
        for nx in edges.get(n,()):
            if nx not in seen: seen.add(nx); q.append(nx)
    return seen

chan = {nm: cone_back(bram_in[nm]) for nm in bram_in}

print("=== FPGA external I/O census ===")
from collections import Counter as C
kinds=C((k,d) for k,d,*_ in io)
for (k,d),n in kinds.most_common(): print(f"  {k:7s} {d:8s} x{n}")

print("\n=== I/O grouped by die edge (col 1=left, col 20=right, row 1=top, row 19=bot) ===")
def edge(r,c):
    if c<=1: return "LEFT"
    if c>=20: return "RIGHT"
    if r<=1: return "TOP"
    if r>=19: return "BOT"
    return "mid"
byedge=defaultdict(C)
for k,d,nm,r,c,net in io: byedge[edge(r,c)][(k,d)]+=1
for e in ("LEFT","RIGHT","TOP","BOT","mid"):
    if byedge[e]: print(f"  {e:5s}: {dict(byedge[e])}")

print("\n=== which channel each ADC/DAC I/O feeds (fwd) or each control I/O reaches ===")
for k,d,nm,r,c,net in io:
    if k in("IDDRC","ODDRC"):
        f=cone_fwd([net]); hit=[ch for ch in chan if (bram_in[ch] & f)]
        print(f"  {k} {nm} (R{r}C{c}) -> channels {hit}")

# control inputs: IBUF nets that land inside a channel cone (what firmware drives)
print("\n=== control/data INPUT pins feeding each channel cone ===")
in_nets=[(nm,r,c,net) for k,d,nm,r,c,net in io if d.startswith("in")]
for ch in sorted(chan):
    feeders=[f"{nm}(R{r}C{c})" for nm,r,c,net in in_nets if net in chan[ch]]
    print(f"  {ch}: {len(feeders)} input pins -> {feeders[:12]}")
# inputs NOT in any acquisition cone = likely MCU control/global
allcone=set().union(*chan.values()) if chan else set()
loose=[f"{nm}(R{r}C{c})" for nm,r,c,net in in_nets if net not in allcone]
print(f"\n  input pins NOT in any BRAM cone (MCU bus / global control?): {len(loose)}")
print("   ", loose[:20])
