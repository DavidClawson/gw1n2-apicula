#!/usr/bin/env python3
"""R3 (osc request): what ARMS / SUSTAINS the scope-channel BRAM writes?

Backward-traces the *control* side of the four sample BRAMs (CLK / CE / OCE /
WRE / RESET and the write address bus) through the routing graph + cell logic
cones back to primary inputs (IBUF pads), so we can name the top-edge MCU-bus
nets that gate capture.

Unlike m_datapath.py (which EXCLUDES high-fanout globals to follow data), this
tool FOLLOWS the control/clock/enable nets — that's the whole point.

Net production in the unpacked netlist:
  `define A B      -> A is an alias of physical wire B
  assign A = B;    -> routing pip, B drives A
  CELL (.O(net))   -> net driven by a cell output port
Backward expansion of a control net: resolve aliases/assigns, and when a net is
a cell output, recurse into that cell's *input* nets (combinational cone), and
for sequential cells also into their own CLK/CE/LSR control nets.
"""
import os, re, sys
from collections import defaultdict, deque

NET = os.path.join(os.path.dirname(__file__), "m5", "scope_unpacked.v")
if not os.path.exists(NET):
    NET = os.path.expanduser("~/m5/scope_unpacked.v")
txt = open(NET).read()
CONST = {"VCC", "VSS", "GND", "VDD"}
norm = lambda w: w[1:] if w.startswith("`") else w

# --- 1. macros (node aliases) ---
alias = {}
for a, b in re.findall(r"^`define\s+(\S+)\s+(\S+)", txt, re.M):
    alias[a] = norm(b)

# --- 2. routing assigns ---
assign_src = {}
for dst, src in re.findall(r"^assign\s+(\S+)\s*=\s*(\S+?);", txt, re.M):
    assign_src[norm(dst)] = norm(src)

# --- 3. cells ---
insts = re.findall(r"^([A-Z][A-Z0-9_]*)\s+(\S+)\s*\((.*?)\);", txt, re.S | re.M)
def ports(body):
    return [(k, norm(v)) for k, v in re.findall(r"\.(\w+)\(([^)]*)\)", body) if v.strip()]
loc_re = re.compile(r"R(\d+)C(\d+)")

# output-port name fragments per primitive family (everything else = input)
OUT_PORTS = {
    "IBUF": {"O"}, "IOBUF": {"O"}, "OBUF": set(),
    "LUT4": {"F"}, "MUX2": {"O"},
    "ALU": {"SUM", "COUT", "F"},
    "DFFE": {"Q"}, "DFFSE": {"Q"}, "DFFRE": {"Q"}, "DFFCE": {"Q"}, "DFFPE": {"Q"},
    "DLE": {"Q"}, "DLCE": {"Q"},
    "IDDRC": {"Q0", "Q1"}, "ODDRC": {"Q0", "Q1"},
}
# control input ports we want to follow for sequential cells
SEQ_CTRL = {"CLK", "CE", "LSR", "CLEAR", "PRESET", "RESET", "SET"}

produced_by = {}          # net -> cell name (cell output)
cell_inputs = defaultdict(list)   # cell -> [(port, net)]
cell_type = {}
cell_loc = {}
ibuf_out = {}             # output net -> ibuf cell name (primary inputs)
for typ, name, body in insts:
    pl = ports(body)
    cell_type[name] = typ
    m = loc_re.search(name)
    cell_loc[name] = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
    fam = typ
    outs = OUT_PORTS.get(fam, {"O", "F", "Q", "Q0", "Q1", "SUM", "COUT"})
    for port, net in pl:
        if net in CONST:
            continue
        if port in outs:
            produced_by[net] = name
        else:
            cell_inputs[name].append((port, net))
    if typ == "IBUF":
        for port, net in pl:
            if port == "O" and net not in CONST:
                ibuf_out[net] = name

def driver_of(net):
    """Return ('alias'|'assign'|'cell'|None, detail) for what drives `net`."""
    net = norm(net)
    if net in alias:
        return ("alias", alias[net])
    if net in assign_src:
        return ("assign", assign_src[net])
    if net in produced_by:
        return ("cell", produced_by[net])
    return (None, None)

def backtrace(start_nets, follow_seq_ctrl=True, max_nodes=200000):
    """Backward BFS from control nets. Returns (ibufs_hit, cells_seen, nets_seen)."""
    seen = set()
    q = deque(norm(n) for n in start_nets if n and norm(n) not in CONST)
    ibufs = {}
    cells = set()
    while q and len(seen) < max_nodes:
        net = q.popleft()
        if net in seen or net in CONST:
            continue
        seen.add(net)
        if net in ibuf_out:
            ibufs[net] = ibuf_out[net]
            continue  # primary input — stop
        kind, det = driver_of(net)
        if kind in ("alias", "assign"):
            q.append(det)
        elif kind == "cell":
            cell = det
            cells.add(cell)
            for port, innet in cell_inputs.get(cell, ()):
                t = cell_type[cell]
                is_seq = t.startswith("DFF") or t in ("DLE", "DLCE")
                if is_seq and port in SEQ_CTRL and not follow_seq_ctrl:
                    continue
                q.append(innet)
    return ibufs, cells, seen

# --- BSRAM control ports of interest (A = write side in SDP scope use) ---
BSRAMS = {"BSRAM_0": "CH1", "BSRAM_1": "?", "BSRAM_2": "?", "BSRAM_3": "CH2"}
WRITE_CTRL = ("CLKA", "CEA", "OCEA", "WREA", "RESETA")
ADDR_A = tuple(f"ADA{i}" for i in range(14))

# map BSRAM name -> {port: net}
bram_ports = {}
for typ, name, body in insts:
    if typ == "BSRAM":
        bram_ports[name] = {k: v for k, v in ports(body)}

print(f"netlist: {NET}")
print(f"IBUF primary inputs: {len(ibuf_out)} nets; cells: {len(cell_type)}; "
      f"aliases: {len(alias)}; assigns: {len(assign_src)}\n")

def edge(cell):
    r, c = cell_loc.get(cell, (-1, -1))
    side = ("TOP" if r == 1 else "BOT" if r == 19 else
            "LEFT" if c == 1 else "RIGHT" if c == 20 else "core")
    return side

for bram, ch in BSRAMS.items():
    if bram not in bram_ports:
        continue
    p = bram_ports[bram]
    print(f"########## {bram} ({ch}) @ R{cell_loc.get(bram)} ##########")
    # write-control nets
    for port in WRITE_CTRL:
        net = p.get(port)
        if not net:
            continue
        ib, cells, nets = backtrace([net])
        kinds = driver_of(net)
        # immediate driver readable form
        chain = []
        cur = net
        for _ in range(6):
            k, d = driver_of(cur)
            if k is None:
                break
            chain.append(f"{cur}->{d}")
            if k == "cell":
                chain[-1] += f"[{cell_type.get(d)}]"
                break
            cur = d
        srcs = sorted(set(ib.keys()))
        ibsumm = ", ".join(f"{n}({edge(c)})" for n, c in sorted(ib.items())) or "—(constant/local)"
        print(f"  {port:7s}= {net}")
        print(f"     immediate: {' | '.join(chain) if chain else '(none)'}")
        print(f"     IBUF cone ({len(ib)}): {ibsumm}")
    # address bus: collect all IBUFs feeding any write-address bit
    addr_nets = [p[a] for a in ADDR_A if p.get(a)]
    ib, cells, nets = backtrace(addr_nets)
    by_side = defaultdict(list)
    for n, c in ib.items():
        by_side[edge(c)].append((n, c))
    print(f"  ADDR(write) cone: {len(addr_nets)} addr nets -> {len(ib)} IBUFs, "
          f"{len(cells)} cells")
    for side in ("TOP", "LEFT", "RIGHT", "BOT", "core"):
        if by_side[side]:
            names = ", ".join(sorted(n for n, _ in by_side[side]))
            print(f"     {side}: {names}")
    # count sequential cells in address cone (counter depth hint)
    seqs = [c for c in cells if cell_type[c].startswith("DFF")]
    print(f"     address-cone registers (DFF*): {len(seqs)}")
    print()

# ===================== R3 deep-dive: CEA gate decomposition =====================
print("\n" + "="*70)
print("CEA gate decomposition (per-input classification)")
print("="*70)

def classify_net(net, depth=12):
    """Walk back from a single net; report first 'interesting' driver:
    IBUF (primary in), DFF (register/counter bit), LUT/ALU (logic), const."""
    cur = norm(net)
    path = []
    for _ in range(depth):
        if cur in CONST:
            return "CONST", cur, path
        if cur in ibuf_out:
            return "IBUF", cur, path
        k, d = driver_of(cur)
        if k is None:
            return "?", cur, path
        if k == "cell":
            t = cell_type.get(d, "?")
            return ("DFF" if t.startswith("DFF") else "LOGIC"), f"{d}[{t}]", path
        path.append(cur)
        cur = d
    return "DEEP", cur, path

CEA_LUTS = {"BSRAM_0": "R13C2_LUT4_3", "BSRAM_3": "R11C17_LUT4_1"}
for bram, lut in CEA_LUTS.items():
    print(f"\n{bram} CEA gate = {lut}:")
    for port, net in cell_inputs.get(lut, ()):
        kind, who, _ = classify_net(net)
        # full IBUF cone of this single input
        ib, cells, _ = backtrace([net])
        ibs = ",".join(sorted(ib)) or "—"
        ndff = sum(1 for c in cells if cell_type[c].startswith("DFF"))
        print(f"   {port}={net:18s} -> {kind:6s} {who:22s} | IBUF cone: {ibs} | DFFs in cone: {ndff}")

# ===================== R3 deep-dive: forward role of the 3 control inputs ========
print("\n" + "="*70)
print("Forward fanout of the control inputs -> first cell port reached")
print("="*70)

# build forward consumer map
consumers = defaultdict(list)
for dst, src in [(d, s) for d, s in re.findall(r"^assign\s+(\S+)\s*=\s*(\S+?);", txt, re.M)]:
    consumers[norm(src)].append(("net", norm(dst)))
for a, b in alias.items():            # A is alias of B: B drives A
    consumers[b].append(("net", a))
for cell, plist in cell_inputs.items():
    for port, net in plist:
        consumers[net].append(("port", cell, port))

def forward_roles(start, max_nodes=60000):
    seen = set([norm(start)])
    q = deque([norm(start)])
    hits = []  # (celltype, port, cellname)
    while q and len(seen) < max_nodes:
        n = q.popleft()
        for c in consumers.get(n, ()):
            if c[0] == "net":
                if c[1] not in seen:
                    seen.add(c[1]); q.append(c[1])
            else:
                _, cell, port = c
                hits.append((cell_type.get(cell, "?"), port, cell))
    return hits

PORTCLASS = {
    "CE": "ENABLE(run/stop)", "CLK": "CLOCK",
    "LSR": "RESET/REARM", "CLEAR": "RESET/REARM", "PRESET": "PRESET/REARM",
    "SET": "PRESET/REARM", "RESET": "RESET/REARM",
}
def role(port):
    return PORTCLASS.get(port, "DATA/logic" if port.startswith(("I", "A", "B", "C", "D")) else port)

from collections import Counter
for net in ("R1C20_Q6", "R19C7_Q6", "R19C18_Q6", "R19C18_F6"):
    hits = forward_roles(net)
    # summarize by (port-role)
    rolec = Counter(role(p) for _, p, _ in hits)
    # specifically: does it reach BRAM control? counter DFF control?
    bram_ctrl = [(t, p) for t, p, c in hits if t == "BSRAM" and p in
                 ("CEA", "WREA", "CLKA", "RESETA", "OCEA", "CE", "WRE", "RESET")]
    dff_ctrl = Counter(p for t, p, c in hits if t.startswith("DFF") and p in
                       ("CE", "LSR", "CLEAR", "PRESET", "SET"))
    print(f"\n{net}: {len(hits)} cell-port endpoints")
    print(f"   role mix: {dict(rolec)}")
    print(f"   -> DFF control ports: {dict(dff_ctrl)}")
    if bram_ctrl:
        print(f"   -> BRAM control ports: {Counter(p for _,p in bram_ctrl)}")

# ============ R3 deep-dive: deep forward role (through combinational logic) ======
print("\n" + "="*70)
print("DEEP forward role: through LUT/MUX/ALU to sequential/BRAM control endpoints")
print("="*70)
COMB = lambda t: t in ("LUT4", "MUX2") or t.startswith("ALU")
# net -> producing cell (already have produced_by); cell -> output nets
cell_outnets = defaultdict(list)
for net, cell in produced_by.items():
    cell_outnets[cell].append(net)

def forward_deep(start, max_nodes=120000):
    seen=set([norm(start)]); q=deque([norm(start)])
    endpoints=[]  # (celltype, port, cell)
    while q and len(seen)<max_nodes:
        n=q.popleft()
        for c in consumers.get(n, ()):
            if c[0]=="net":
                if c[1] not in seen: seen.add(c[1]); q.append(c[1])
            else:
                _, cell, port = c; t=cell_type.get(cell,"?")
                if COMB(t):
                    # pass through: enqueue this comb cell's outputs
                    for o in cell_outnets.get(cell, ()):
                        if o not in seen: seen.add(o); q.append(o)
                else:
                    endpoints.append((t, port, cell))
    return endpoints

for net in ("R1C20_Q6", "R19C7_Q6", "R19C18_Q6"):
    eps = forward_deep(net)
    dffc = Counter(p for t,p,c in eps if t.startswith("DFF") and p in ("CE","LSR","CLEAR","PRESET","SET"))
    dffd = sum(1 for t,p,c in eps if t.startswith("DFF") and p=="D")
    bramc= Counter(p for t,p,c in eps if t=="BSRAM")
    print(f"\n{net}: {len(eps)} sequential/BRAM endpoints")
    print(f"   DFF control: {dict(dffc)}   DFF data(D): {dffd}")
    print(f"   BRAM ports : {dict(bramc)}")

# CEA LUT INIT recovery
print("\n--- LUT INIT params on the CEA gate path (BSRAM_0) ---")
for lut in ("R13C2_LUT4_3", "R13C2_LUT4_5", "R12C2_LUT4_1"):
    m = re.search(r"defparam "+re.escape(lut)+r"\.INIT\s*=\s*([^;]+);", txt)
    print(f"   {lut}.INIT = {m.group(1) if m else '(not found)'}")

# ===================== R3: map control pads -> physical QN48 pins ================
print("\n" + "="*70)
print("Physical pin mapping (GW1N-1P5C / QFN48XF)")
print("="*70)
import json
PJ = "/tmp/gw1n2_pinout.json"
try:
    pj = json.load(open(PJ))
    ROWS, COLS = pj["rows"], pj["cols"]
    # IOB-name -> (pin, funcs)
    name2pin = {v[0]: (p, v[1]) for p, v in pj["pinout"].items()}
    def loc_to_iobname(r, c, idx):   # r,c are 1-based netlist coords
        if c == 1:        return f"IOL{r}{idx}"
        if c == COLS:     return f"IOR{r}{idx}"
        if r == 1:        return f"IOT{c}{idx}"
        if r == ROWS:     return f"IOB{c}{idx}"
        return None
    def pad_pin(net):
        cell = ibuf_out.get(net)
        if not cell:
            return None
        r, c = cell_loc[cell]
        idx = "B" if cell.endswith("_B") else "A"
        nm = loc_to_iobname(r, c, idx)
        if nm in name2pin:
            pin, funcs = name2pin[nm]
            return f"pin {pin} ({nm}{', '+'/'.join(funcs) if funcs else ''})"
        return f"{nm} (not bonded on QFN48XF)"
    print("\nThe three capture-control inputs:")
    for net, note in [("R1C20_Q6", "MASTER run/re-arm: 70 DFF.CE + 8 DFF.SET"),
                      ("R19C7_Q6", "secondary: 2 DFF.CE"),
                      ("R19C18_Q6", "minor: 1 DFF.D"),
                      ("R19C18_F6", "(sibling pad, unused in fabric)")]:
        print(f"   {net:12s} -> {pad_pin(net)}    [{note}]")
    print("\nFull MCU/control IBUF pad map (all input pads):")
    rows_out = []
    for net, cell in ibuf_out.items():
        r, c = cell_loc[cell]
        idx = "B" if cell.endswith("_B") else "A"
        nm = loc_to_iobname(r, c, idx)
        pin, funcs = name2pin.get(nm, ("?", []))
        rows_out.append((int(pin) if str(pin).isdigit() else 999, pin, nm,
                         "/".join(funcs), f"R{r}C{c}", net))
    for _, pin, nm, funcs, loc, net in sorted(rows_out):
        print(f"   pin {pin:>3}  {nm:8s} {loc:7s} {net:14s} {funcs}")
except FileNotFoundError:
    print("  (pinout JSON not found; run the mars export first)")

# ===================== R3 bonus / R1 feed: READ-side (B-port) trace =============
print("\n" + "="*70)
print("READ-side (B-port) trace: how 0x04/0x05 clocks the buffer out to the MCU")
print("="*70)
import json as _json
_pj = _json.load(open("/tmp/gw1n2_pinout.json"))
_ROWS, _COLS = _pj["rows"], _pj["cols"]
_name2pin = {v[0]: (p, v[1]) for p, v in _pj["pinout"].items()}
def _iobname(r, c, idx):
    if c == 1: return f"IOL{r}{idx}"
    if c == _COLS: return f"IOR{r}{idx}"
    if r == 1: return f"IOT{c}{idx}"
    if r == _ROWS: return f"IOB{c}{idx}"
    return f"R{r}C{c}{idx}"
def _padpin(net):
    cell = ibuf_out.get(net)
    if not cell: return net
    r, c = cell_loc[cell]; idx = "B" if cell.endswith("_B") else "A"
    nm = _iobname(r, c, idx)
    if nm in _name2pin:
        pin, funcs = _name2pin[nm]
        return f"pin{pin}/{nm}" + (f"({'/'.join(funcs)})" if funcs else "")
    return f"{nm}(unbonded)"

# output pads (to MCU)
out_pads = {}
for typ, name, body in insts:
    if typ in ("OBUF", "IOBUF"):
        r, c = cell_loc[name]; idx = "B" if name.endswith("_B") else "A"
        nm = _iobname(r, c, idx)
        pp = _name2pin.get(nm)
        out_pads[name] = f"{nm}" + (f"=pin{pp[0]}({'/'.join(pp[1])})" if pp else "")

READ_CTRL = ("CLKB", "CEB", "OCEB", "WREB", "RESETB")
ADB = tuple(f"ADB{i}" for i in range(14))
for bram, ch in (("BSRAM_0", "CH1 / opcode 0x04"), ("BSRAM_3", "CH2 / opcode 0x05")):
    p = bram_ports[bram]
    print(f"\n#### {bram} ({ch}) read side ####")
    for port in READ_CTRL:
        net = p.get(port)
        if not net: continue
        ib, cells, _ = backtrace([net])
        chain = []; cur = net
        for _ in range(5):
            k, d = driver_of(cur)
            if k is None: break
            chain.append(d if k != "cell" else f"{d}[{cell_type.get(d)}]")
            if k == "cell": break
            cur = d
        pins = ", ".join(sorted(_padpin(n) for n in ib)) or "—(local/global/const)"
        print(f"   {port:7s}={net:30s} src:{' -> '.join(chain[:3]) or 'const'}")
        if ib: print(f"           IBUF cone: {pins}")
    adb_nets = [p[a] for a in ADB if p.get(a)]
    ib, cells, _ = backtrace(adb_nets)
    ndff = sum(1 for c in cells if cell_type[c].startswith("DFF"))
    print(f"   ADB(read addr): {len(adb_nets)} bits -> {len(ib)} IBUFs, {ndff} DFFs in cone")
    print(f"           pins: {', '.join(sorted(_padpin(n) for n in ib)) or '—'}")
    do_nets = [v for k, v in p.items() if k.startswith("DO") and v not in CONST]
    eps = []
    for dn in do_nets: eps += forward_deep(dn)
    out_hit = Counter(out_pads.get(c, c) for t, port, c in eps if t in ("OBUF", "IOBUF"))
    print(f"   DO read-data ({len(do_nets)} bits) -> output pads: {dict(out_hit) or 'none direct (goes via logic/regs)'}")
