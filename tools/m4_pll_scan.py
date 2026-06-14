#!/usr/bin/env python3
"""Pin down the GW1N-2 (GW1N-1P5C) PLL portmap layout in the extended .dat table.

The base read_portmap stores the PLL block contiguously:
    PllIn(36) | PllOut(5) | PllInDlt(36) | PllOutDlt(5) | PllClkin(6 clkins)
For GW1N-1P5C the base copy is all -1, but the real block lives in the appended
table at 0x7b4a8. Find the contiguous block by its signature:
  * PllIn   : 36 int16, mostly small wire indices (0..400) + some -1
  * PllOut  : 5 int16, wire indices in the rPLL output range (~30..45)
  * PllInDlt: 36 int16, tiny cell offsets (-2..2)
  * PllOutDlt:5 int16, tiny cell offsets (-2..2)
Cross-check field-by-field against GW1NZ-1's known-good values for sanity.
"""
import os, struct
from pathlib import Path
import sys; sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
from apycula import dat_parser

GH = os.environ["GOWINHOME"]
def datbytes(v): return Path(f"{GH}/IDE/share/device/{v}/{v}.dat").read_bytes()
def arr16(b, off, n): return list(struct.unpack_from("<%dh" % n, b, off))

zd = dat_parser.Datfile(Path(f"{GH}/IDE/share/device/GW1NZ-1/GW1NZ-1.dat"))
print("GW1NZ-1 base PllIn   :", list(zd.portmap["PllIn"]))
print("GW1NZ-1 base PllOut  :", list(zd.portmap["PllOut"]))
print("GW1NZ-1 base PllInDlt:", list(zd.portmap["PllInDlt"]))
print("GW1NZ-1 base PllOutDlt:", list(zd.portmap["PllOutDlt"]))
print("GW1NZ-1 base PllClkin:", zd.portmap["PllClkin"])

b = datbytes("GW1N-1P5C")
RS = 0x7b4a8

def looks_in(a):    # 36 wire indices
    ok = [v for v in a if -1 <= v < 450]
    small_neg = [v for v in a if v < -1]
    return len(ok) == 36 and not small_neg and any(v > 0 for v in a)
def looks_out(a):   # 5 output wire indices, rPLL range ~30..50
    return all(0 <= v < 60 for v in a)
def looks_dlt(a):   # tiny cell offsets
    return all(-3 <= v <= 3 for v in a)

print("\n--- searching for PllIn(36)|PllOut(5)|PllInDlt(36)|PllOutDlt(5) ---")
hits = []
for off in range(RS, len(b) - 82*2, 2):
    pin = arr16(b, off, 36)
    pout = arr16(b, off + 72, 5)
    pindlt = arr16(b, off + 82, 36)
    poutdlt = arr16(b, off + 154, 5)
    if looks_in(pin) and looks_out(pout) and looks_dlt(pindlt) and looks_dlt(poutdlt):
        hits.append((off, pin, pout, pindlt, poutdlt))

print(f"composite hits: {len(hits)}")
for off, pin, pout, pindlt, poutdlt in hits[:6]:
    print(f"\n  >> off {off:#x} (RS+{off-RS:#x})")
    print(f"     PllIn   : {pin}")
    print(f"     PllOut  : {pout}")
    print(f"     PllInDlt: {pindlt}")
    print(f"     PllOutDlt:{poutdlt}")
