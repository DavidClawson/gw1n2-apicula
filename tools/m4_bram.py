#!/usr/bin/env python3
"""M4b: validate GW1N-2 BRAM (BSRAM) decode on the read path.

Synthesize a behavioural single-port RAM with the Gowin oracle (gw_sh maps it to
a BSRAM macro), unpack with gowin_unpack -d GW1N-2, and confirm a BSRAM primitive
is recovered with config. This is the same decode M5 (scope bitstream) needs.

Also a regression check: the earlier AND gate must still unpack cleanly after the
PLL/chipdb changes.
"""
import os, sys, subprocess, re
from collections import Counter
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
import fuzz

APICULA = os.path.expanduser("~/gw1n2-apicula/tools/apicula")
PN = "GW1N-UV1P5QN48XFC7/I6"

# 256 x 8 single-port synchronous RAM -> Gowin infers a BSRAM block.
BRAM_V = """
module top (input clk, input we, input [7:0] addr, input [7:0] din, output reg [7:0] dout);
    (* ram_style = "block" *) reg [7:0] mem [0:255];
    always @(posedge clk) begin
        if (we) mem[addr] <= din;
        dout <= mem[addr];
    end
endmodule
"""

AND_V = ("module top(input wire a, input wire b, output wire y);\n"
         "  (* syn_keep=1 *) LUT4 #(.INIT(16'h8888)) u (.I0(a),.I1(b),.I2(1'b0),.I3(1'b0),.F(y));\n"
         "endmodule\n")
AND_CST = 'IO_LOC "a" 9;\nIO_LOC "b" 10;\nIO_LOC "y" 14;\n'


def unpack(fs, d, tag):
    out = f"{d}/o{tag}.v"
    r = subprocess.run(
        ["python3", "-m", "apycula.gowin_unpack", "-d", "GW1N-2", fs, "-o", out],
        capture_output=True, text=True, cwd=APICULA)
    return (open(out).read() if os.path.exists(out) else ""), r.stderr


def prim_hist(txt):
    return Counter(re.findall(r"^([A-Z][A-Z0-9_]*) \S+ \(", txt, re.M))


print("=== BRAM design (auto-placed) ===")
try:
    fs, d = fuzz.synth(BRAM_V, "", PN)   # empty CST -> gw_sh auto-places pins
    txt, err = unpack(fs, d, "bram")
    h = prim_hist(txt)
    bram = {k: v for k, v in h.items() if "BSRAM" in k or "RAM" in k or k in
            ("SP", "SDP", "DP", "SDPB", "DPB", "SPX9", "ROM", "pROM", "DPX9")}
    print("  unpack stderr tail:", err.strip().splitlines()[-1] if err.strip() else "(clean)")
    print("  BRAM-ish primitives recovered:", bram if bram else "NONE")
    # show any BSRAM instance + its defparams
    for m in re.finditer(r"^((?:SP|SDP|DP|DPB|SDPB|ROM|pROM|SPX9|DPX9|BSRAM\w*) \S+ \(.*?\);)",
                         txt, re.S | re.M):
        print("   ", " ".join(m.group(1).split())[:160])
    dp = [l for l in txt.splitlines() if "defparam" in l and re.search(r"(BSRAM|SP|SDP|DP|ROM)", l)]
    print("  sample BRAM defparams:", dp[:6])
except Exception as e:
    print("  ERROR:", str(e)[:400])

print("\n=== regression: AND gate still unpacks ===")
fs, d = fuzz.synth(AND_V, AND_CST, PN)
txt, err = unpack(fs, d, "and")
h = prim_hist(txt)
init = re.search(r"INIT = 16'h([0-9a-fA-F]+)", txt)
print("  LUT4 count:", h.get("LUT4"), " OBUF:", h.get("OBUF"),
      " an INIT:", init.group(1) if init else None,
      " stderr:", "(clean)" if not err.strip() else err.strip().splitlines()[-1])
