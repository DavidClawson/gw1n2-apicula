#!/usr/bin/env python3
"""M3 probe: see what gowin_unpack emits for a routed design on GW1N-2.

A single LUT4 with inputs on near pins and output on a far pin forces the
signal to route across multiple tiles. We dump the (non-DFFSE-noise) output so
the connectivity checker can be written against the real netlist shape.
"""
import os, sys, subprocess, re
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
import fuzz

PN = "GW1N-UV1P5QN48XFC7/I6"

V = (
    "module top(input wire a, input wire b, output wire y);\n"
    "  (* syn_keep=1 *) LUT4 #(.INIT(16'h6996)) u (.I0(a), .I1(b), .I2(1'b0), .I3(1'b0), .F(y));\n"
    "endmodule\n"
)
CST = 'IO_LOC "a" 9;\nIO_LOC "b" 10;\nIO_LOC "y" 40;\n'

fs, d = fuzz.synth(V, CST, PN)
out = d + "/out.v"
r = subprocess.run(
    ["python3", "-m", "apycula.gowin_unpack", "-d", "GW1N-2", fs, "-o", out],
    capture_output=True, text=True,
    cwd=os.path.expanduser("~/gw1n2-apicula/tools/apicula"),
)
txt = open(out).read()
print("=== unpack stderr tail ===")
print(r.stderr[-600:])
print("=== assigns:", len(re.findall(r"^assign ", txt, re.M)))
print("=== bel instance lines (excl DFFSE):",
      len([l for l in txt.splitlines() if re.match(r"^\w+ \w+ \(", l) and "DFFSE" not in l]))
print("=== lines mentioning LUT ===")
for l in txt.splitlines():
    if "LUT" in l:
        print(l)
print("=== lines mentioning 6996 / our INIT ===")
for l in txt.splitlines():
    if "6996" in l or "9669" in l:
        print(l)
print("=== IOBUF/IBUF/OBUF instance lines ===")
for l in txt.splitlines():
    if re.search(r"\b(IOBUF|IBUF|OBUF|TBUF)\b", l):
        print(l)
