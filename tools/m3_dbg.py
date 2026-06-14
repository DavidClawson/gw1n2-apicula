#!/usr/bin/env python3
"""Debug: how is the INPUT net (pad -> LUT input) represented in the unpack?"""
import os, sys, subprocess, re
from collections import defaultdict, deque
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
import fuzz, m3_routing as M

PN = "GW1N-UV1P5QN48XFC7/I6"
fs, d = fuzz.synth(M.vsrc(), M.cstsrc(('9', '10', '40')), PN)
txt = M.unpack("GW1N-2", fs, d)
edges, lut, obufs, ibufs = M.parse_netlist(txt)

# reverse edges
rev = defaultdict(set)
for s, ds in edges.items():
    for x in ds:
        rev[x].add(s)

print("LUT:", lut)
print("ibuf count:", len(ibufs), " sample:", ibufs[:6])

# What drives each LUT input? walk backward a few levels.
def back(node, depth=8):
    seen={node}; q=deque([(node,0)]); frontier=[]
    while q:
        n,dp=q.popleft()
        if dp>=depth: continue
        for p in rev.get(n,()):
            if p not in seen:
                seen.add(p); q.append((p,dp+1))
    return seen

for inp in lut["inputs"]:
    drivers = rev.get(inp, set())
    print(f"\nLUT input {inp}: directly driven by {drivers}")
    reach = back(inp, 10)
    hit = [w for w in reach if "IB" in w or "IBUF" in w or w in ibufs]
    print(f"   within 10 back-hops, IBUF-ish wires seen: {hit[:10]}")

# Forward from each ibuf: does any reach a LUT input?
tset=set(lut["inputs"])
for ib in ibufs:
    seen={ib}; q=deque([(ib,0)])
    while q:
        n,dp=q.popleft()
        if n in tset:
            print(f"\nIBUF wire {ib} REACHES LUT input {n} at depth {dp}")
            break
        if dp>=12: continue
        for nx in edges.get(n,()):
            if nx not in seen:
                seen.add(nx); q.append((nx,dp+1))

# Show raw assign lines that mention a LUT input
print("\n--- assign lines mentioning", lut["inputs"][0], "---")
for l in txt.splitlines():
    if lut["inputs"][0] in l and l.strip().startswith("assign"):
        print(l)

# Where else does the backtick node R12C1_E11 appear?
for w in ["R12C1_E11", "R12C2_X04"]:
    print(f"\n=== occurrences of {w} (assign/IBUF/wire) ===")
    for l in txt.splitlines():
        s = l.strip()
        if w in s and (s.startswith("assign") or "IBUF" in s or s.startswith("wire")):
            print("  ", s[:100])

# IBUF instance blocks
print("\n=== first 3 IBUF blocks ===")
for b in re.findall(r"(IBUF\s+\S+\s*\(.*?\);)", txt, re.S)[:3]:
    print("  ", " ".join(b.split())[:140])
