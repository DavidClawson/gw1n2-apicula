#!/usr/bin/env python3
"""M4a oracle: validate the GW1N-2 rPLL portmap.

Synthesize a minimal rPLL with the Gowin oracle (CLKIN from a pin, CLKOUT to a
pin), unpack with gowin_unpack -d GW1N-2, and confirm:
  * an RPLLA instance is emitted (i.e. the bel has a usable portmap), and
  * its CLKIN / CLKOUT ports are wired (routed), not floating.
If the reused-from-GW1NZ-1 portmap is correct, the PLL decodes with connected
clock ports; a wrong portmap would leave them empty / mis-routed.
"""
import os, sys, subprocess, re
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
import fuzz

APICULA = os.path.expanduser("~/gw1n2-apicula/tools/apicula")
PN = "GW1N-UV1P5QN48XFC7/I6"

V = """
module top (input wire clk, output wire clkout);
    wire gnd = 1'b0;
    rPLL pll (
        .CLKOUT(clkout), .CLKIN(clk), .CLKFB(gnd),
        .RESET(gnd), .RESET_P(gnd),
        .FBDSEL({gnd,gnd,gnd,gnd,gnd,gnd}),
        .IDSEL({gnd,gnd,gnd,gnd,gnd,gnd}),
        .ODSEL({gnd,gnd,gnd,gnd,gnd,gnd}),
        .DUTYDA({gnd,gnd,gnd,gnd}),
        .PSDA({gnd,gnd,gnd,gnd}),
        .FDLY({gnd,gnd,gnd,gnd})
    );
    defparam pll.FCLKIN = "27";
    defparam pll.IDIV_SEL = 0;
    defparam pll.FBDIV_SEL = 3;
    defparam pll.ODIV_SEL = 8;
    defparam pll.CLKFB_SEL = "internal";
endmodule
"""
CST = 'IO_LOC "clk" 9;\nIO_LOC "clkout" 14;\n'


def main():
    try:
        fs, d = fuzz.synth(V, CST, PN)
    except RuntimeError as e:
        print("SYNTH FAILED:\n", str(e)[-1500:])
        return
    out = d + "/pll.v"
    r = subprocess.run(["python3", "-m", "apycula.gowin_unpack", "-d", "GW1N-2", fs, "-o", out],
                       capture_output=True, text=True, cwd=APICULA)
    warns = [l for l in r.stderr.splitlines() if "Unknown attr" in l or "Traceback" in l]
    print("unpack warnings:", warns[:6] if warns else "(none)")
    txt = open(out).read() if os.path.exists(out) else ""
    # find RPLLA instance block
    m = re.search(r"^(RPLLA\s+(\S+)\s*\((.*?)\));", txt, re.S | re.M)
    if not m:
        print("RESULT: NO RPLLA instance emitted -- portmap still not usable.")
        # any PLL mention?
        print("  PLL-ish lines:", [l for l in txt.splitlines() if "PLL" in l][:4])
        return
    body = " ".join(m.group(3).split())
    ports = dict(re.findall(r"\.(\w+)\(([^)]*)\)", body))
    print(f"RESULT: RPLLA instance '{m.group(2)}' emitted.")
    print(f"  CLKIN  = {ports.get('CLKIN')}")
    print(f"  CLKOUT = {ports.get('CLKOUT')}")
    wired = [k for k, v in ports.items() if v and v not in ("VCC", "VSS", "GND")]
    print(f"  wired ports ({len(wired)}): {wired}")
    # defparams (config attrs decoded)
    dp = re.findall(r"defparam\s+" + re.escape(m.group(2)) + r"\.(\w+)\s*=\s*([^;]+);", txt)
    print(f"  decoded config defparams ({len(dp)}): {dp[:12]}")


if __name__ == "__main__":
    main()
