#!/usr/bin/env python3
"""R3 follow-up §4 (osc): re-arm condition logic.

Questions:
 - Does the capture re-arm depend on IOR1B (run line) ALONE, or is it gated by the
   SPI control register bit (D<-SI) and/or other inputs? -> explains why toggling
   PB11 (osc's IOR1B candidate) low->high did NOT re-arm.
 - Level vs edge? Polarity?
Method: build the graph, locate the DFFs whose CE/SET are reached by IOR1B, read the
LUT (INIT + inputs) that immediately drives those control ports, and test which of
{IOR1B, SI-register-Q, IOB7B} co-feed them.
"""
import os, re
from collections import defaultdict, deque, Counter

NET = os.path.join(os.path.dirname(__file__), "m5", "scope_unpacked.v")
txt = open(NET).read()
CONST = {"VCC", "VSS", "GND", "VDD"}
norm = lambda w: w[1:] if w.startswith("`") else w
alias = {a: norm(b) for a, b in re.findall(r"^`define\s+(\S+)\s+(\S+)", txt, re.M)}
assign_src = {norm(d): norm(s) for d, s in re.findall(r"^assign\s+(\S+)\s*=\s*(\S+?);", txt, re.M)}
insts = re.findall(r"^([A-Z][A-Z0-9_]*)\s+(\S+)\s*\((.*?)\);", txt, re.S | re.M)
INIT = {m[0]: m[1] for m in re.findall(r"defparam\s+(\S+)\.INIT\s*=\s*([^;]+);", txt)}

OUT = {"IBUF": {"O"}, "IOBUF": {"O"}, "LUT4": {"F"}, "MUX2": {"O"},
       "ALU": {"SUM", "COUT", "F"}, "DFFE": {"Q"}, "DFFSE": {"Q"}, "DFFRE": {"Q"},
       "DFFCE": {"Q"}, "DFFPE": {"Q"}, "DLE": {"Q"}, "DLCE": {"Q"},
       "IDDRC": {"Q0", "Q1"}, "ODDRC": {"Q0", "Q1"},
       "BSRAM": {f"DO{i}" for i in range(36)} | {f"DOA{i}" for i in range(18)} | {f"DOB{i}" for i in range(18)}}
prod = {}; cin = defaultdict(list); ctype = {}; cports = {}
for t, n, b in insts:
    ctype[n] = t
    pl = [(p, norm(v)) for p, v in re.findall(r"\.(\w+)\(([^)]*)\)", b) if v.strip()]
    cports[n] = dict(pl)
    for port, net in pl:
        if net in CONST: continue
        if port in OUT.get(t, {"O", "F", "Q", "Q0", "Q1", "SUM", "COUT"}): prod[net] = n
        else: cin[n].append((port, net))

def drv(net):
    net = norm(net)
    if net in alias: return ("a", alias[net])
    if net in assign_src: return ("a", assign_src[net])
    if net in prod: return ("c", prod[net])
    return (None, None)

def src_cell(net):
    """resolve a net through aliases/assigns to the cell that produces it (or None)."""
    cur = norm(net)
    for _ in range(40):
        k, d = drv(cur)
        if k == "c": return d
        if k == "a": cur = d
        else: return None
    return None

# forward reachable set (through everything) from a start net
consumers = defaultdict(list)
for d, s in [(norm(d), norm(s)) for d, s in re.findall(r"^assign\s+(\S+)\s*=\s*(\S+?);", txt, re.M)]:
    consumers[s].append(d)
for a, b in alias.items():
    consumers[b].append(a)
cell_out = defaultdict(list)
for net, c in prod.items():
    cell_out[c].append(net)

def forward_through_comb(start):
    """reach cell input PORTS; pass through LUT/MUX/ALU outputs; stop at seq/BRAM/OBUF."""
    seen = {norm(start)}; q = deque([norm(start)]); hits = []
    portmap = defaultdict(list)
    for c, pl in cin.items():
        for port, net in pl: portmap[net].append((c, port))
    while q:
        n = q.popleft()
        for nx in consumers.get(n, ()):
            if nx not in seen: seen.add(nx); q.append(nx)
        for cell, port in portmap.get(n, ()):
            t = ctype[cell]
            if t in ("LUT4", "MUX2") or t.startswith("ALU"):
                for o in cell_out.get(cell, ()):
                    if o not in seen: seen.add(o); q.append(o)
            else:
                hits.append((t, port, cell))
    return hits, seen

IOR1B = "R1C20_Q6"; IOB7B = "R19C7_Q6"; SI = "R19C18_Q6"; SCLK_loc = "R19C5"

print("="*70); print("§4 RE-ARM CONDITION ANALYSIS"); print("="*70)

# --- 1. The SPI control register: DFF whose D <- SI ---
print("\n[1] SPI control-register bit (the D<-SI flop):")
si_hits, _ = forward_through_comb(SI)
spi_regs = [(c, port) for (t, port, c) in si_hits if t.startswith("DFF") and port == "D"]
spi_reg_q = []
for c, _ in spi_regs:
    clk = cports[c].get("CLK"); q = [o for o in cell_out.get(c, [])]
    clk_cell = src_cell(clk) if clk else None
    clk_loc = ""
    if clk_cell:
        m = re.search(r"R(\d+)C(\d+)", clk_cell);
    print(f"    {c} [{ctype[c]}]  D<-SI  CLK={clk}  Q={q}")
    spi_reg_q += q
print(f"    -> SPI register Q nets: {spi_reg_q}")

# --- 2. DFFs whose CE or SET are reached by IOR1B ---
print("\n[2] Capture-engine flops controlled by IOR1B:")
hits, _ = forward_through_comb(IOR1B)
ce_cells = [(c) for (t, port, c) in hits if t.startswith("DFF") and port == "CE"]
set_cells = [(c) for (t, port, c) in hits if t.startswith("DFF") and port in ("SET", "PRESET")]
print(f"    {len(ce_cells)} DFF.CE, {len(set_cells)} DFF.SET in IOR1B forward cone")

# --- 3. For the SET (re-arm) flops, read the LUT driving SET: is SI-reg / IOB7B also an input? ---
def cone_inputs(net, depth=40):
    """which of the key primary signals are in this net's backward cone?"""
    seen = set(); q = deque([norm(net)]); found = set(); lut_inits = []
    keymap = {IOR1B: "IOR1B", IOB7B: "IOB7B", SI: "SI"}
    keymap.update({q_: "SPIreg" for q_ in spi_reg_q})
    while q:
        x = q.popleft()
        if x in seen: continue
        seen.add(x)
        if x in keymap: found.add(keymap[x]); continue
        k, d = drv(x)
        if k == "a": q.append(d)
        elif k == "c":
            cell = d
            if ctype[cell] == "LUT4" and cell in INIT:
                lut_inits.append((cell, INIT[cell]))
            for _, nn in cin.get(cell, ()): q.append(nn)
    return found, lut_inits

print("\n[3] Re-arm (DFF.SET) gate dependencies — does SET need SI-reg too?")
seen_lut = set()
for c in set_cells[:8]:
    setnet = cports[c].get("SET") or cports[c].get("PRESET")
    lut = src_cell(setnet)
    found, _ = cone_inputs(setnet)
    init = INIT.get(lut, "?")
    print(f"    {c}.SET <- {lut}[{ctype.get(lut)}] INIT={init}  depends on: {sorted(found)}")

print("\n[4] Sample of CE (run-enable) flops — dependencies:")
for c in ce_cells[:6]:
    cenet = cports[c].get("CE")
    lut = src_cell(cenet)
    found, _ = cone_inputs(cenet)
    print(f"    {c}.CE <- {lut}[{ctype.get(lut)}] INIT={INIT.get(lut,'?')}  depends on: {sorted(found)}")

# --- 5. Does the BSRAM CEA gate depend on the SPI register? ---
print("\n[5] BRAM write-enable (CEA) gate dependency on SPI register:")
for bram, gate in (("BSRAM_0", None), ("BSRAM_3", None)):
    # CEA net
    bbody = [b for t, n, b in insts if n == bram][0]
    cea = norm(dict(re.findall(r"\.(\w+)\(([^)]*)\)", bbody))["CEA"])
    found, inits = cone_inputs(cea)
    print(f"    {bram}.CEA depends on: {sorted(found)}")

# --- 6. Exact inputs of the re-arm AND + polarity, SPI-reg clock, data-ready OBUFs ---
print("\n" + "="*70); print("§4 DETAIL: re-arm AND inputs, SPI clock, data-ready output")
print("="*70)

def resolve_one(net, depth=40):
    """walk back one signal path; return (label, n_inversions_estimate, terminal)."""
    cur = norm(net); inv = 0
    for _ in range(depth):
        for tag, name in ((IOR1B,"IOR1B"),(IOB7B,"IOB7B"),(SI,"SI"),("R16C9_Q3","SPIreg(D<-SI)")):
            if cur == tag: return name, cur
        k, d = drv(cur)
        if k == "a": cur = d
        elif k == "c":
            cell = d; t = ctype[cell]
            if t == "IBUF": return f"PAD:{cell}", cur
            if t.startswith("DFF"): return f"FLOP:{cell}", cur
            if t == "BSRAM": return f"BRAM:{cell}", cur
            # comb: follow first non-const input
            ins = [n for _,n in cin.get(cell,())]
            if not ins: return f"{t}:{cell}", cur
            cur = ins[0]
        else:
            return f"net:{cur}", cur
    return f"deep:{cur}", cur

print("\n[6a] Re-arm AND gate R6C16_LUT4_7 (INIT=0x8000 = I0&I1&I2&I3):")
for port, net in cin.get("R6C16_LUT4_7", ()):
    lab, term = resolve_one(net)
    print(f"     {port} = {net:18s} <- {lab}")

print("\n[6b] SPI control-register flop R16C9_DFFE_3 (D<-SI):")
c = "R16C9_DFFE_3"
for port in ("D","CLK","CE","SET","CLEAR"):
    if port in cports[c]:
        net = cports[c][port]; lab,_ = resolve_one(net)
        print(f"     {port} = {net:18s} <- {lab}")
# what clocks it? resolve CLK to a pad
clk = cports[c].get("CLK")
clk_src = src_cell(clk) if clk else None
print(f"     (CLK cell: {clk_src} type {ctype.get(clk_src)})")

print("\n[6c] Output pads (FPGA->MCU) — candidates for data-ready (PC0):")
for t, n, b in insts:
    if t in ("OBUF","IOBUF"):
        p = dict(re.findall(r"\.(\w+)\(([^)]*)\)", b))
        inet = norm(p.get("I",""))
        r,col = (re.search(r"R(\d+)C(\d+)", n).groups())
        # backward cone: does it carry counter/terminal (buffer-full) or BRAM data?
        seen=set(); q=deque([inet]); src_kinds=Counter(); ndff=0; brams=set()
        while q:
            x=q.popleft()
            if x in seen or x in CONST: continue
            seen.add(x)
            k,d=drv(x)
            if k=="a": q.append(d)
            elif k=="c":
                tt=ctype[d]
                if tt=="BSRAM": brams.add(d); continue
                if tt.startswith("DFF"): ndff+=1
                if tt=="IBUF": src_kinds["IBUF:"+d]+=1; continue
                for _,nn in cin.get(d,()): q.append(nn)
        lab,_ = resolve_one(inet)
        print(f"     {t} {n} (R{r}C{col}) I={inet} <- {lab} | cone: {ndff} DFFs, BRAMs={sorted(brams)}")
