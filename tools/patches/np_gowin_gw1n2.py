#!/usr/bin/env python3
"""Patch nextpnr's himbaechel gowin_arch_gen.py for GW1N-2 (WIP).

Two changes, both idempotent:
  1) create_pll_tiletype: skip the PLL bel when it isn't in the chipdb. GW1N-2's
     PLL lives in the still-unparsed partType-1 extended table (M4), so db has no
     'RPLLA' bel. Emit the PLL tile without a PLL bel so logic/routing/IO designs
     still build (a blinky doesn't use the PLL).
  2) simple_io set: add 'GW1N-2' alongside 'GW1NZ-1' (same small-part IO family /
     GW1N-1P5C die) so its IOBs are generated like the reference device.

Usage: python3 np_gowin_gw1n2.py /path/to/gowin_arch_gen.py
"""
import sys

f = sys.argv[1]
src = open(f).read()
orig = src

# 1) PLL skip
needle = "    portmap = db[y, x].bels[pll_name].portmap\n    pll = tt.create_bel(\"PLL\", bel_type, z = PLL_Z)"
repl = (
    "    if pll_name not in db[y, x].bels:\n"
    "        # GW1N-2 (WIP): PLL not yet in chipdb (partType-1 extended table / M4).\n"
    "        # Emit the tile without a PLL bel so logic/routing/IO still round-trip.\n"
    "        tdesc.tiletype = tiletype\n"
    "        return tt\n"
    "    portmap = db[y, x].bels[pll_name].portmap\n"
    "    pll = tt.create_bel(\"PLL\", bel_type, z = PLL_Z)"
)
if needle in src:
    src = src.replace(needle, repl, 1)
elif "GW1N-2 (WIP): PLL not yet in chipdb" in src:
    pass  # already patched
else:
    print("WARN: PLL needle not found (generator changed?)")

# 2) simple_io set
io_needle = "chip.name in {'GW1N-1', 'GW1NZ-1', 'GW1N-4'}"
io_repl = "chip.name in {'GW1N-1', 'GW1NZ-1', 'GW1N-2', 'GW1N-4'}"
if io_needle in src:
    src = src.replace(io_needle, io_repl, 1)
elif "'GW1N-2'" in src and "simplio_rows" in src:
    pass  # already patched
else:
    print("WARN: simple_io needle not found")

if src != orig:
    open(f, "w").write(src)
    print("patched", f)
else:
    print("no change (already patched?)", f)
