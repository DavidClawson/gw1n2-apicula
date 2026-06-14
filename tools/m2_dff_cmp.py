#!/usr/bin/env python3
"""Does gowin_unpack decode DFF *mode* on the known-good GW1NZ-1, or also dump
all-DFFSE like it does for GW1N-2? Run a DFFC (async clear) on each and compare."""
import os, sys, subprocess, re
from collections import Counter
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
import fuzz

def run(device, pn):
    v = ("module top (input wire clk, input wire d, input wire x, output wire q);\n"
         "  DFFC ff (.CLK(clk), .D(d), .Q(q), .CLEAR(x));\n"
         "endmodule\n")
    cst = 'IO_LOC "clk" 9;\nIO_LOC "d" 10;\nIO_LOC "q" 11;\n'  # x auto-placed
    fs, dd = fuzz.synth(v, cst, pn)
    out = dd + "/out.v"
    subprocess.run(["python3","-m","apycula.gowin_unpack","-d",device,fs,"-o",out],
                   capture_output=True, text=True,
                   cwd=os.path.expanduser("~/gw1n2-apicula/tools/apicula"))
    txt = open(out).read() if os.path.exists(out) else ""
    hist = Counter(re.findall(r"^(DFF[A-Z]*) ", txt, re.M))
    # find the DFF instance(s) that have CLEAR/RESET/SET ports wired (i.e. the placed one)
    insts = re.findall(r"^(DFF[A-Z]*) (\S+) \((.*?)\);", txt, re.S | re.M)
    placed = [(t, n) for (t, n, body) in insts
              if re.search(r"\.(CLEAR|RESET|SET|PRESET|CE)\s*\(\s*[a-zA-Z]", body)]
    print(f"== {device} (DFFC) ==")
    print(f"   DFF type histogram: {dict(hist)}")
    print(f"   DFF instances with a set/reset/ce port wired: {placed[:5]}")

run("GW1NZ-1", "GW1NZ-LV1QN48C6/I5")
run("GW1N-2",  "GW1N-UV1P5QN48XFC7/I6")
