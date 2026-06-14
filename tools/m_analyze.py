#!/usr/bin/env python3
"""Analyze the unpacked scope netlist: resource utilization / headroom, and
spatial distribution (to test the 'scope + DMM, side by side' hypothesis).

Every instance is named R{row}C{col}_<type>_<n>, so we can recover where each
used cell physically sits on the 19x20 die and how full the fabric is.
"""
import os, re, sys
from collections import Counter, defaultdict

NET = os.path.expanduser("~/m5/scope_unpacked2.v")
if not os.path.exists(NET):
    NET = os.path.expanduser("~/m5/scope_unpacked.v")
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
from apycula.chipdb import load_chipdb

db = load_chipdb(os.path.expanduser("~/gw1n2-apicula/tools/apicula/apycula/GW1N-2.msgpack.xz"))
ROWS, COLS = db.rows, db.cols
txt = open(NET).read()

# instances: TYPE R{r}C{c}_NAME ( ...
inst = re.findall(r"^([A-Z][A-Z0-9_]*)\s+R(\d+)C(\d+)_\S*\s*\(", txt, re.M)
by_type = Counter(t for t, r, c in inst)

# DFFSE is the structural per-CLS artifact; real DFFs are the others
def is_real_dff(t): return t.startswith("DFF") and t != "DFFSE"

# --- headroom: capacity from chipdb vs used ---
# count physical LUT/DFF slots in the fabric (CLS bels) from the chipdb
cap_lut = cap_ff = 0
for r in range(ROWS):
    for c in range(COLS):
        t = db.tiles[db.grid[r][c]]
        for b in (t.bels or {}):
            if re.fullmatch(r"LUT\d", b): cap_lut += 1
            if re.fullmatch(r"DFF\d", b): cap_ff += 1
cap_bsram = sum(1 for r in range(ROWS) for c in range(COLS)
                if "BSRAM" in (db.tiles[db.grid[r][c]].bels or {}))

used_lut = by_type.get("LUT4", 0) + sum(v for t, v in by_type.items() if t.startswith("LUT") and t != "LUT4")
used_alu = by_type.get("ALU", 0)            # ALU occupies LUT slots
used_logic = used_lut + used_alu
used_ff = sum(v for t, v in by_type.items() if is_real_dff(t))
used_bsram = by_type.get("BSRAM", 0)

print("=== RESOURCE UTILIZATION / HEADROOM ===")
print(f"  LUT4 capacity (chipdb CLS slots): {cap_lut}")
print(f"  logic used: {used_lut} LUT4 + {used_alu} ALU = {used_logic}  "
      f"({100*used_logic/cap_lut:.0f}% of LUT slots)")
print(f"  FF used: {used_ff} / {cap_ff} ({100*used_ff/cap_ff:.0f}%)")
print(f"  BSRAM used: {used_bsram} / {cap_bsram}")
print(f"  all real-instance types: {dict(by_type)}")

# --- spatial: occupancy per (region) ---
print("\n=== SPATIAL OCCUPANCY (used logic+FF cells per tile) ===")
occ = defaultdict(int)
for t, r, c in inst:
    if t == "DFFSE":     # skip structural artifact
        continue
    if t.startswith(("LUT", "DFF", "ALU", "MUX")):
        occ[(int(r), int(c))] += 1
# print a coarse map: rows x cols, density char
print("   cols ->", "".join(f"{c%10}" for c in range(1, COLS + 1)))
for r in range(1, ROWS + 1):
    line = []
    for c in range(1, COLS + 1):
        n = occ.get((r, c), 0)
        line.append("." if n == 0 else ("#" if n >= 8 else str(min(n, 7))))
    print(f"   r{r:2d}      " + "".join(line))

# halves: is usage split? compare left/right and top/bottom mass
def mass(pred):
    return sum(v for (r, c), v in occ.items() if pred(r, c))
total = sum(occ.values())
print("\n=== balance (of placed logic/FF/mux cells) ===")
print(f"  total placed cells: {total}")
print(f"  left half  (c<= {COLS//2}): {mass(lambda r,c: c<=COLS//2)}  "
      f"right half: {mass(lambda r,c: c>COLS//2)}")
print(f"  top half   (r<= {ROWS//2}): {mass(lambda r,c: r<=ROWS//2)}  "
      f"bottom half: {mass(lambda r,c: r>ROWS//2)}")

# BSRAM + DDR-IO locations (functional anchors)
print("\n=== anchor blocks (BSRAM / DDR I/O) locations ===")
for kind in ("BSRAM", "IDDRC", "ODDRC", "IOBUF", "OBUF"):
    locs = sorted({(int(r), int(c)) for t, r, c in inst if t == kind})
    if locs:
        print(f"  {kind:7s} ({len(locs)}): {locs[:20]}")
