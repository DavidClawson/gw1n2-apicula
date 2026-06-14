#!/usr/bin/env python3
"""Remove the (blocked, unvalidated) GW1N-2 PLL additions from a copy of chipdb.py
so a PLL-free PR3 patch (pinout/IO/OSC) can be generated. The PLL work stays
documented as a future PR; it is not part of the validated GW1N-2 contribution.

Usage: python3 strip_pll_blocks.py <chipdb.py path (modified in place)>
"""
import sys

f = sys.argv[1]
src = open(f).read()

BLOCKS = [
    # fse_pll GW1N-2 case
    ("""    elif device in {'GW1N-2'}:
        # GW1N-2 (GW1N-1P5C die): single rPLL, tile type 50 (M4 bring-up).
        if ttyp in {50}:
            bel = bels.setdefault('RPLLA', Bel())
""", ""),
    # dat_portmap PllIn -1 guard
    ("""                        # GW1N-2 (GW1N-1P5C, partType 1): the base-region PllIn/PllOut
                        # are all -1 -- the real PLL portmap lives in the appended
                        # extended table at 0x7b4a8 (located, full decode is an M4
                        # follow-up needing the EDA oracle). Skip unmapped ports so the
                        # PLL bel + config fuses still build.
                        if dat.portmap['PllIn'][idx] < 0:
                            continue
""", ""),
    # dat_portmap PllOut -1 guard
    ("""                        if dat.portmap['PllOut'][idx] < 0:    # GW1N-2: see PllIn note above
                            continue
""", ""),
]

for old, new in BLOCKS:
    if old not in src:
        print("WARN: block not found:\n", old[:80])
    src = src.replace(old, new, 1)

open(f, "w").write(src)
print("stripped PLL blocks from", f)
