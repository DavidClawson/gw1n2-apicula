#!/usr/bin/env python3
"""Clock-domain analysis of the unpacked scope netlist. Two independent functions
(scope + DMM) loaded side by side would tend to show as distinct clock domains
whose flip-flops occupy distinct regions of the die."""
import os, re
from collections import Counter, defaultdict

NET = os.path.expanduser("~/m5/scope_unpacked2.v")
if not os.path.exists(NET):
    NET = os.path.expanduser("~/m5/scope_unpacked.v")
txt = open(NET).read()

# real DFF instances (not DFFSE): grab name (for R{r}C{c}) + CLK net
dff = re.findall(r"^(DFF[A-Z]+)\s+R(\d+)C(\d+)_(\S+)\s*\((.*?)\);", txt, re.S | re.M)
clk_of = {}
clk_locs = defaultdict(list)
clk_count = Counter()
for typ, r, c, nm, body in dff:
    if typ == "DFFSE":
        continue
    m = re.search(r"\.CLK\(([^)]*)\)", " ".join(body.split()))
    if not m:
        continue
    clk = m.group(1)
    # normalise: strip backtick + the R*C* tile prefix to get the clock spine name
    base = clk.lstrip("`")
    spine = re.sub(r"^R\d+C\d+_", "", base)
    clk_count[spine] += 1
    clk_locs[spine].append((int(r), int(c)))

print("=== CLOCK DOMAINS (by spine net feeding real DFF.CLK) ===")
for spine, n in clk_count.most_common():
    locs = clk_locs[spine]
    rows = [r for r, c in locs]
    cols = [c for r, c in locs]
    print(f"  {spine:14s} {n:4d} FFs   rows {min(rows)}-{max(rows)} "
          f"(median {sorted(rows)[len(rows)//2]})  cols {min(cols)}-{max(cols)}")

# top/bottom split per clock domain (center row 10 is architectural)
print("\n=== each domain's FFs: top (r<=9) vs bottom (r>=11) ===")
for spine, n in clk_count.most_common(8):
    top = sum(1 for r, c in clk_locs[spine] if r <= 9)
    bot = sum(1 for r, c in clk_locs[spine] if r >= 11)
    print(f"  {spine:14s} top={top:4d}  bottom={bot:4d}")
