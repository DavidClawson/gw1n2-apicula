#!/usr/bin/env python3
"""M2: verify GW1N-2 DFF config bits.

Instantiate each Gowin DFF primitive variant (plain, clock-enable, sync/async
set/reset, negedge) and report what gowin_unpack recovers. The default decode of
an unused cell is DFFSE, so we look at how the *placed* DFF and the bitstream
change per variant. Also diff-fuzz the cleanest isolated case (DFF vs DFFN =
clock-edge config) to locate that fuse.
"""
import os, sys, subprocess, re
from collections import Counter
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
import fuzz

PN = "GW1N-UV1P5QN48XFC7/I6"

# primitive body + whether it needs the extra control pin x
VARIANTS = {
    "DFF":  ("DFF  ff (.CLK(clk), .D(d), .Q(q));", False),
    "DFFN": ("DFFN ff (.CLK(clk), .D(d), .Q(q));", False),
    "DFFE": ("DFFE ff (.CLK(clk), .D(d), .Q(q), .CE(x));", True),
    "DFFR": ("DFFR ff (.CLK(clk), .D(d), .Q(q), .RESET(x));", True),
    "DFFS": ("DFFS ff (.CLK(clk), .D(d), .Q(q), .SET(x));", True),
    "DFFC": ("DFFC ff (.CLK(clk), .D(d), .Q(q), .CLEAR(x));", True),
    "DFFP": ("DFFP ff (.CLK(clk), .D(d), .Q(q), .PRESET(x));", True),
}

def vsrc(body, needs_x):
    ports = "input wire clk, input wire d, output wire q"
    if needs_x:
        ports += ", input wire x"
    return f"module top ({ports});\n  {body}\nendmodule\n"

def cst(needs_x):
    s = 'IO_LOC "clk" 9;\nIO_LOC "d" 10;\nIO_LOC "q" 11;\n'
    if needs_x:
        s += 'IO_LOC "x" 12;\n'
    return s

def unpack(fs, d):
    out = d + "/out.v"
    subprocess.run(["python3","-m","apycula.gowin_unpack","-d","GW1N-2",fs,"-o",out],
                   capture_output=True, text=True,
                   cwd=os.path.expanduser("~/gw1n2-apicula/tools/apicula"))
    return open(out).read() if os.path.exists(out) else ""

def dff_hist(txt):
    return Counter(re.findall(r"^(DFF[A-Z]*) ", txt, re.M))

bitmaps = {}
print("=== DFF variant recovery (histogram of DFF primitive types in unpack) ===")
base_hist = None
for name, (body, needs_x) in VARIANTS.items():
    fs, d = fuzz.synth(vsrc(body, needs_x), cst(needs_x), PN)
    bitmaps[name] = fuzz.bitmap(fs)
    h = dff_hist(unpack(fs, d))
    if name == "DFF":
        base_hist = h
    # show the delta vs the plain-DFF design so the *placed* FF's mode stands out
    delta = {k: h[k] - (base_hist[k] if base_hist else 0) for k in set(h) | set(base_hist or {})}
    delta = {k: v for k, v in delta.items() if v}
    print(f"  {name:5s}: {dict(h)}   delta-vs-DFF: {delta}")

print("\n=== diff-fuzz: DFF vs DFFN (clock-edge config, identical ports) ===")
diffs = fuzz.diff(bitmaps["DFF"], bitmaps["DFFN"])
print(f"  {len(diffs)} bitstream bits differ; positions: {[(r,c) for r,c,*_ in diffs][:12]}")

print("\n=== diff-fuzz: DFF vs DFFC (async clear) ===")
diffs = fuzz.diff(bitmaps["DFF"], bitmaps["DFFC"])
print(f"  {len(diffs)} bitstream bits differ; positions: {[(r,c) for r,c,*_ in diffs][:16]}")
