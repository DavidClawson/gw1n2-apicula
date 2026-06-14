#!/usr/bin/env python3
"""Structural dump of the GW1N-1P5C extended .dat table head (0x7b4a8) to map the
PLL portmap fields. Print as rows of int16 with offsets so the PllIn / PllOut /
delta arrays can be identified by eye, annotated against GW1NZ-1's known values.
"""
import os, struct
from pathlib import Path
import sys; sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
from apycula import dat_parser

GH = os.environ["GOWINHOME"]
def datb(v): return Path(f"{GH}/IDE/share/device/{v}/{v}.dat").read_bytes()
def a16(b, off, n): return list(struct.unpack_from("<%dh" % n, b, off))

zd = dat_parser.Datfile(Path(f"{GH}/IDE/share/device/GW1NZ-1/GW1NZ-1.dat"))
print("GW1NZ-1 PllIn   :", list(zd.portmap["PllIn"]))
print("GW1NZ-1 PllInDlt:", list(zd.portmap["PllInDlt"]))
print("GW1NZ-1 PllOut  :", list(zd.portmap["PllOut"]))
print("GW1NZ-1 PllOutDlt:",list(zd.portmap["PllOutDlt"]))
print("GW1NZ-1 PllClkin:", zd.portmap["PllClkin"])

b = datb("GW1N-1P5C")
RS = 0x7b4a8
print(f"\n=== GW1N-1P5C extended table @ {RS:#x}, first 160 int16 (10/row) ===")
for r in range(16):
    base = RS + r * 20
    vals = a16(b, base, 10)
    print(f"  RS+{r*20:#05x}: " + " ".join(f"{v:5d}" for v in vals))
