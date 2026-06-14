#!/usr/bin/env python3
"""M2: map ALL 16 GW1N-2 LUT4 truth-table fuses by single-bit diff-fuzzing.

For each INIT bit i, synth base ^ (1<<i), diff vs base, and record the flipped
bitstream position. A clean result = exactly one fuse per INIT bit, all in one
tile, and gowin_unpack recovering the exact INIT.
"""
import os, sys, subprocess, re
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
import fuzz

PN  = "GW1N-UV1P5QN48XFC7/I6"
CST = ('IO_LOC "a" 9;\nIO_LOC "b" 10;\nIO_LOC "c" 11;\n'
       'IO_LOC "d" 12;\nIO_LOC "y" 14;\n')
BASE = 0x6996

def vsrc(init):
    return (f"module top (input wire a, input wire b, input wire c, input wire d, output wire y);\n"
            f"  LUT4 #(.INIT(16'h{init:04x})) u (.I0(a), .I1(b), .I2(c), .I3(d), .F(y));\n"
            f"endmodule\n")

def rec_init(fs, d):
    out = d + "/out.v"
    subprocess.run(["python3","-m","apycula.gowin_unpack","-d","GW1N-2",fs,"-o",out],
                   capture_output=True, text=True,
                   cwd=os.path.expanduser("~/gw1n2-apicula/tools/apicula"))
    m = re.findall(r"LUT4_\d+\.INIT = 16'h([0-9a-fA-F]+)", open(out).read()) if os.path.exists(out) else []
    return m[0] if m else None

base_fs, base_d = fuzz.synth(vsrc(BASE), CST, PN)
base_bm = fuzz.bitmap(base_fs)
print(f"base INIT=0x{BASE:04x}, recovered=0x{rec_init(base_fs, base_d)}\n")

fuse_map = {}
clean = True
for i in range(16):
    var = BASE ^ (1 << i)
    fs, d = fuzz.synth(vsrc(var), CST, PN)
    diffs = fuzz.diff(base_bm, fuzz.bitmap(fs))
    rec = rec_init(fs, d)
    ok = rec is not None and int(rec, 16) == var
    clean = clean and len(diffs) == 1 and ok
    pos = (diffs[0][0], diffs[0][1]) if len(diffs) == 1 else [(r, c) for r, c, *_ in diffs]
    fuse_map[i] = pos
    print(f"INIT[{i:2d}]: {len(diffs)} fuse(s) {pos}   recovered=0x{rec} {'OK' if ok else 'MISMATCH'}")

print("\nLUT4 fuse map (INIT bit -> bitstream row,col):")
for i in range(16):
    print(f"  bit{i:2d} -> {fuse_map[i]}")
print(f"\nRESULT: {'ALL 16 fuses cleanly mapped & verified' if clean else 'some bits not clean — inspect above'}")
