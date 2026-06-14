#!/usr/bin/env python3
"""M2 experiment: locate GW1N-2 LUT4 truth-table fuses by diff-fuzzing.

Synthesize the same single-LUT4 design with different INIT values and diff the
resulting bitstreams. A one-bit INIT change should flip a small, localized set
of bitstream bits == the physical location of that truth-table fuse.
"""
import os, sys, subprocess, re
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
import fuzz

PN  = "GW1N-UV1P5QN48XFC7/I6"
CST = ('IO_LOC "a" 9;\nIO_LOC "b" 10;\nIO_LOC "c" 11;\n'
       'IO_LOC "d" 12;\nIO_LOC "y" 14;\n')

def vsrc(init):
    return (f"module top (input wire a, input wire b, input wire c, input wire d, output wire y);\n"
            f"  LUT4 #(.INIT(16'h{init})) u (.I0(a), .I1(b), .I2(c), .I3(d), .F(y));\n"
            f"endmodule\n")

def unpack_init(fs, workdir):
    out = workdir + "/out.v"
    subprocess.run(["python3", "-m", "apycula.gowin_unpack", "-d", "GW1N-2", fs, "-o", out],
                   capture_output=True, text=True,
                   cwd=os.path.expanduser("~/gw1n2-apicula/tools/apicula"))
    if not os.path.exists(out):
        return None
    m = re.findall(r"LUT4_\d+\.INIT = 16'h([0-9a-fA-F]+)", open(out).read())
    return m[0] if m else None

base_init = "6996"
print(f"base design: single LUT4 INIT=0x{base_init}")
base_fs, base_d = fuzz.synth(vsrc(base_init), CST, PN)
base_bm = fuzz.bitmap(base_fs)
print(f"  base unpacks to LUT4 INIT=0x{unpack_init(base_fs, base_d)}")
print(f"  base bitmap size: {len(base_bm)} rows x {len(base_bm[0])} cols\n")

# flip individual INIT bits relative to base and observe bitstream diffs
cases = [
    ("6997", "INIT bit 0"),
    ("6986", "INIT bit 4"),
    ("e996", "INIT bit 15"),
    ("6996", "identical (control)"),
]
for init, label in cases:
    fs, d = fuzz.synth(vsrc(init), CST, PN)
    bm = fuzz.bitmap(fs)
    diffs = fuzz.diff(base_bm, bm)
    rec = unpack_init(fs, d)
    positions = [(r, c) for (r, c, o, n) in diffs]
    print(f"0x{base_init} -> 0x{init} [{label}]: {len(diffs)} bitstream bits differ; "
          f"recovered INIT=0x{rec}")
    if 0 < len(diffs) <= 12:
        print(f"    positions: {positions}")
