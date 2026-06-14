#!/usr/bin/env python3
"""M4 recon: what does the GW1N-2 chipdb already have for PLL/BRAM, and which
tile types does the GW1N-1P5C die expose for PLL ('P') and BRAM ('B')?

Compares against GW1NZ-1 (known-good, 1 PLL + BRAM, same GW1N-1 family).
"""
import os, sys
from pathlib import Path
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
from apycula import chipdb as C
from apycula import fse_parser, dat_parser
from apycula.chipdb import load_chipdb

GOWINHOME = os.environ["GOWINHOME"]
DEVDIR = GOWINHOME + "/IDE/share/device"

CASES = [
    ("GW1N-2",  "GW1N-1P5C"),   # apicula name, vendor device folder
    ("GW1NZ-1", "GW1NZ-1"),
]


def func_ttypes(dev_grid_dat, fse, dat, letter):
    try:
        return sorted(C.get_tile_types_by_func(dev_grid_dat, dat, fse, letter))
    except Exception as e:
        return f"ERR {e}"


for apiname, vendor in CASES:
    print(f"\n===== {apiname} (vendor {vendor}) =====")
    with open(f"{DEVDIR}/{vendor}/{vendor}.fse", "rb") as _f:
        fse = fse_parser.read_fse(_f, apiname)
    dat = dat_parser.Datfile(Path(f"{DEVDIR}/{vendor}/{vendor}.dat"))
    # a throwaway dev object just to call get_tile_types_by_func (needs .grid)
    # from_fse builds it; reuse the loaded chipdb's grid instead.
    db = load_chipdb(os.path.expanduser(
        f"~/gw1n2-apicula/tools/apicula/apycula/{apiname}.msgpack.xz"))
    # PLL/BRAM tile types from the .dat grid letters
    print("  PLL tile types ('P'):", func_ttypes(db, fse, dat, 'P'))
    print("  BRAM tile types ('B'):", func_ttypes(db, fse, dat, 'B'))
    print("  BRAM aux ('b'):       ", func_ttypes(db, fse, dat, 'b'))
    # what bels exist across the grid
    from collections import Counter
    belct = Counter()
    for ttyp, t in db.tiles.items():
        for b in (t.bels or {}):
            belct[b] += 1
    interesting = {k: v for k, v in belct.items()
                   if any(s in k for s in ("PLL", "BSRAM", "OSC", "DLL", "GSR"))}
    print("  special bels in tiles:", interesting)
    print("  pad_pll entries:", len(getattr(db, "pad_pll", {}) or {}),
          list((getattr(db, "pad_pll", {}) or {}).items())[:3])
    print("  chip_flags:", getattr(db, "chip_flags", "<none>"))
    # extra_func special cells
    ef = getattr(db, "extra_func", {}) or {}
    efkinds = Counter()
    for loc, d in ef.items():
        for k in d:
            efkinds[k] += 1
    print("  extra_func kinds:", dict(efkinds))
