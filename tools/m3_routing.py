#!/usr/bin/env python3
"""M3: validate GW1N-2 routing decode by route-sensitivity diff-fuzzing.

A static connectivity graph can't cleanly resolve Apicula's netlist because
inter-tile wires are expressed through the node/alias system (a leading backtick,
e.g. `assign R12C2_A0 = `R12C1_E11;`). So instead we validate routing the way
the fuzzer validates everything else: change ONE thing and confirm both the
bitstream and the decode track it.

Experiment
----------
Same kept LUT4 (inputs a,b on fixed pins), output y placed on several different
far pins. For each placement:
  * the LUT.F -> output-buffer assign chain is a clean, connected path that ends
    at the OBUF for that pin (output routing is plain assigns -> extractable);
  * moving the output pin changes the decoded route (different wire path);
  * the bitstream routing fuses differ between placements, while re-running the
    SAME placement gives a 0-bit diff (deterministic control).

If routing fuses were mis-located or pip read-back were wrong, the LUT.F path
would not reach the correct OBUF and/or the decoded route would not change with
the pin. Run on GW1N-2 and on the known-good GW1NZ-1 as a control.
"""
import os, sys, subprocess, re
from collections import defaultdict, deque
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
import fuzz

APICULA = os.path.expanduser("~/gw1n2-apicula/tools/apicula")
CONST = {"VCC", "VSS", "GND", "VDD"}


def norm(w):
    """Normalise an inter-tile node reference: drop the leading backtick."""
    return w[1:] if w.startswith("`") else w


def vsrc():
    return (
        "module top(input wire a, input wire b, output wire y);\n"
        "  (* syn_keep=1 *) LUT4 #(.INIT(16'h6996)) u "
        "(.I0(a), .I1(b), .I2(1'b0), .I3(1'b0), .F(y));\n"
        "endmodule\n"
    )


def cstsrc(ypin, apin='9', bpin='10'):
    return f'IO_LOC "a" {apin};\nIO_LOC "b" {bpin};\nIO_LOC "y" {ypin};\n'


def unpack(device, fs, d, tag=""):
    out = f"{d}/out{tag}.v"
    subprocess.run(
        ["python3", "-m", "apycula.gowin_unpack", "-d", device, fs, "-o", out],
        capture_output=True, text=True, cwd=APICULA,
    )
    return open(out).read() if os.path.exists(out) else ""


def parse_netlist(txt):
    edges = defaultdict(set)               # src -> {dst}, backticks normalised
    for dst, src in re.findall(r"^assign\s+(\S+)\s*=\s*(\S+?);", txt, re.M):
        s, d = norm(src), norm(dst)
        if s in CONST or d in CONST:
            continue
        edges[s].add(d)

    insts = re.findall(r"^([A-Z][A-Z0-9_]*)\s+(\S+)\s*\((.*?)\);", txt, re.S | re.M)
    luts, obufs, ibufs = [], [], []
    for typ, name, body in insts:
        ports = {k: norm(v) for k, v in re.findall(r"\.(\w+)\(\s*([^)]*?)\s*\)", body)}
        if typ == "LUT4":
            ins = [ports[k] for k in ("I0", "I1", "I2", "I3")
                   if ports.get(k) and ports[k] not in CONST]
            if ports.get("F"):
                luts.append({"name": name, "inputs": ins, "out": ports["F"]})
        elif typ in ("OBUF", "TBUF"):
            if ports.get("I") and ports["I"] not in CONST:
                obufs.append({"name": name, "wire": ports["I"]})
        elif typ == "IBUF":
            if ports.get("O") and ports["O"] not in CONST:
                ibufs.append({"name": name, "wire": ports["O"]})
    return edges, luts, obufs, ibufs


def path(edges, start, target, maxdepth=300):
    """Shortest forward path of wires from start to target, or None."""
    if start == target:
        return [start]
    prev = {start: None}
    q = deque([start])
    while q:
        n = q.popleft()
        for nx in edges.get(n, ()):
            if nx not in prev:
                prev[nx] = n
                if nx == target:
                    out = [nx]
                    while prev[out[-1]] is not None:
                        out.append(prev[out[-1]])
                    return list(reversed(out))
                q.append(nx)
    return None


def analyze(device, pn, ypins):
    print(f"\n========== {device} ({pn}) ==========")
    runs = {}   # ypin -> (bitmap, route, in_drivers, obuf_name)
    for yp in ypins:
        try:
            fs, d = fuzz.synth(vsrc(), cstsrc(yp), pn)
        except RuntimeError:
            print(f"  pin {yp}: synth failed (invalid pad) — skipping")
            continue
        bm = fuzz.bitmap(fs)
        txt = unpack(device, fs, d, tag=yp)
        edges, luts, obufs, ibufs = parse_netlist(txt)
        if len(luts) != 1 or len(obufs) != 1:
            print(f"  pin {yp}: expected 1 LUT/1 OBUF, got {len(luts)}/{len(obufs)} — skip")
            continue
        lut, ob = luts[0], obufs[0]
        rt = path(edges, lut["out"], ob["wire"])
        in_drv = {i: sorted(s for s in edges if i in edges[s]) for i in lut["inputs"]}
        # only the driven (real) inputs
        in_drv = {i: v for i, v in in_drv.items() if v}
        runs[yp] = (bm, rt, in_drv, ob["name"], lut)
        ok = rt is not None
        print(f"  pin {yp}: LUT {lut['name']}.F -> OBUF {ob['name']} : "
              f"{'CONNECTED len=%d' % len(rt) if ok else 'NO PATH'}")
        if ok:
            print(f"           route: {' -> '.join(rt)}")
        print(f"           driven LUT inputs: "
              f"{ {k: v for k, v in in_drv.items()} }")

    # control: re-synth the first placement, expect 0-bit bitstream diff
    if ypins:
        yp0 = next(iter(runs)) if runs else None
    pins = list(runs)
    print("\n  --- route sensitivity ---")
    for i in range(len(pins)):
        for j in range(i + 1, len(pins)):
            a, b = pins[i], pins[j]
            nbits = len(fuzz.diff(runs[a][0], runs[b][0]))
            same_route = runs[a][1] == runs[b][1]
            print(f"  pins {a} vs {b}: bitstream bits differ = {nbits}; "
                  f"decoded route differs = {not same_route}")
    return runs


def control(device, pn, yp):
    fs1, d1 = fuzz.synth(vsrc(), cstsrc(yp), pn)
    fs2, d2 = fuzz.synth(vsrc(), cstsrc(yp), pn)
    n = len(fuzz.diff(fuzz.bitmap(fs1), fuzz.bitmap(fs2)))
    print(f"  control (pin {yp} synth'd twice): bitstream bits differ = {n} "
          f"({'deterministic' if n == 0 else 'NONDETERMINISTIC!'})")


def report_traced(device, runs):
    traced = {yp: r for yp, r in runs.items() if r[1] is not None}
    print(f"\n  >>> {device}: {len(traced)}/{len(runs)} placements fully traced "
          f"(LUT.F -> correct OBUF via assign-only path):")
    for yp, r in traced.items():
        print(f"      pin {yp}: OBUF {r[3]}  len={len(r[1])}")
    # are the traced routes mutually distinct?
    routes = [tuple(r[1]) for r in traced.values()]
    print(f"      distinct traced routes: {len(set(routes))} of {len(routes)}")


if __name__ == "__main__":
    # GW1N-2: sweep a wide set of candidate output pads to collect several
    # fully-traceable divergent routes (invalid pads self-skip).
    GW2_PINS = ['40', '41', '42', '43', '47', '48', '30', '31', '32',
                '33', '25', '27', '20', '21', '15', '16']
    runs = analyze("GW1N-2", "GW1N-UV1P5QN48XFC7/I6", GW2_PINS)
    if runs:
        report_traced("GW1N-2", runs)
        control("GW1N-2", "GW1N-UV1P5QN48XFC7/I6", next(iter(runs)))
    # GW1NZ-1 control: a smaller set is enough to show identical behaviour
    runs_z = analyze("GW1NZ-1", "GW1NZ-LV1QN48C6/I5", ['40', '42', '44', '38'])
    if runs_z:
        report_traced("GW1NZ-1", runs_z)
        control("GW1NZ-1", "GW1NZ-LV1QN48C6/I5", next(iter(runs_z)))
