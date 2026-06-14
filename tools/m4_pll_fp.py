#!/usr/bin/env python3
"""Fingerprint-locate the GW1N-2 PLL portmap in the partType-1 extended table.

Hypothesis: the rPLL port->local-wire map is a property of the primitive/tile,
so GW1N-2 (GW1N-1P5C) should carry ~the same PllIn/PllOut values GW1NZ-1 has in
its base .dat, just relocated into the extended table at 0x7b4a8.

Slide a window over the extended region and score each position against the
GW1NZ-1 reference arrays. A high-scoring contiguous block pins the offsets for
PllIn(36) | PllOut(5) | PllInDlt(36) | PllOutDlt(5).
"""
import os, struct
from pathlib import Path
import sys; sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
from apycula import dat_parser

GH = os.environ["GOWINHOME"]
def datb(v): return Path(f"{GH}/IDE/share/device/{v}/{v}.dat").read_bytes()
def a16(b, off, n): return list(struct.unpack_from("<%dh" % n, b, off))

zd = dat_parser.Datfile(Path(f"{GH}/IDE/share/device/GW1NZ-1/GW1NZ-1.dat"))
ref_in   = list(zd.portmap["PllIn"])     # 36
ref_out  = list(zd.portmap["PllOut"])    # 5
ref_indlt= list(zd.portmap["PllInDlt"])  # 36
ref_outdlt=list(zd.portmap["PllOutDlt"]) # 5
print("ref PllIn   :", ref_in)
print("ref PllOut  :", ref_out)

b = datb("GW1N-1P5C")
RS = 0x7b4a8

def score(a, ref):
    return sum(1 for x, y in zip(a, ref) if x == y)

# 1) exact-ish match for PllIn (36)
print("\n--- best PllIn(36) matches in extended table ---")
cands = []
for off in range(RS, len(b) - 72, 2):
    a = a16(b, off, 36)
    s = score(a, ref_in)
    if s >= 12:
        cands.append((s, off, a))
cands.sort(reverse=True)
for s, off, a in cands[:6]:
    print(f"  score {s}/36 @ {off:#x} (RS+{off-RS:#x}): {a}")

# 2) For the top PllIn hit, check the following PllOut(5) / deltas layout
if cands:
    s, off, a = cands[0]
    print(f"\n--- layout probe around top PllIn @ {off:#x} ---")
    for label, rel, n, ref in [("PllIn", 0, 36, ref_in),
                               ("PllOut@+72", 72, 5, ref_out),
                               ("PllInDlt@+82", 82, 36, ref_indlt),
                               ("PllOutDlt@+154", 154, 5, ref_outdlt)]:
        vals = a16(b, off + rel, n)
        print(f"  {label:16s}: {vals}   (matches ref: {score(vals, ref)}/{len(ref)})")

# 3) Also locate PllOut fingerprint independently
print("\n--- best PllOut(5) matches ---")
oc = []
for off in range(RS, len(b) - 10, 2):
    a = a16(b, off, 5)
    s = score(a, ref_out)
    if s >= 3:
        oc.append((s, off, a))
oc.sort(reverse=True)
for s, off, a in oc[:6]:
    print(f"  score {s}/5 @ {off:#x} (RS+{off-RS:#x}): {a}")
