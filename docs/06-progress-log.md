# 06 — Progress log

## 2026-06-13 — Environment up + GW1N-2 recognized & unpacking (M0 ✅, M1 ✅)

Went from "GW1N-2 unrecognized" to "a real GW1N-2 bitstream unpacks through Apicula"
in one session. All work runs on **mars** (`david@mars.local`); see
`docs/01-environment-setup.md`, `docs/05-needs-david.md`, and the project memories.

### Environment (M0)
- Gowin EDA **Education V1.9.11.03** installed at `~/gowin/V1.9.11.03_Education`
  (license-free). Standard edition needs a license — avoided.
- Headless `gw_sh` works with: `QT_QPA_PLATFORM=offscreen` +
  `LD_PRELOAD=<system libfreetype>` (bundled 2019 libs are too old for Ubuntu 24.04).
  Codified in `tools/gowin-env.sh`; `apycula/codegen.py` patched to honor
  `$GOWIN_LD_PRELOAD`.
- Apicula editable-installed; OSS-CAD-Suite fetched to `tools/oss-cad-suite`.
- GW1NZ-1 chipdb rebuilt from scratch: 34/36 Device fields identical to the official
  PyPI build → toolchain + parsers proven against this vendor version.

### The key discovery
The GW1N-2 die is sold license-free in Education only as **GW1N-1P5C** (same silicon
— shared `.fse` family). **Verified**: synthesizing for `GW1N-UV1P5QN48XFC7/I6` emits
device-ID `06 00 00 00 01 20 68 1b` = **IDCODE 0x0120681B**, exactly the scope's.
So we drive the oracle as GW1N-1P5C and label the Apicula device `GW1N-2`.

The real reason GW1N-2 was never finished upstream: its `.dat` is **partType 1**,
which `dat_parser.py` explicitly rejected. Reverse-engineered: partType-1 files
(538638 B) are byte-identical to partType-0 (505000 B) in the fixed-offset region
parsed by Apicula, and only *append* a ~33 KB extended table at `0x7b4a8`. Treating
partType 1 like partType 0 parses the grid/IO/logic cleanly (asserts all pass).

### Changes (7 files, ~52 lines — see `tools/patches/0000-gw1n2-bringup-ALL.patch`)
- `bslib.py` — recognize IDCODE 0x0120681B.
- `chipdb_builder.py` — `DEVICE_PARAMS['GW1N-2']` (device=GW1N-1P5C, pkg=QFN48XF,
  pn=GW1N-UV1P5QN48XFC7/I6), `_chip_id['GW1N-2']`, GSR at db[0,0]/C4, Makefile target.
- `dat_parser.py` — accept partType 1 (parse as partType 0; extended table TBD).
- `chipdb.py` — `json_pinout`/`get_pins` for GW1N-1P5C; OSCO osc stub; non-fatal
  unknown-IO-cfg for GW1N-2.
- `gowin_unpack.py` — `_packages['GW1N-2']='QFN48XF'`.
- `codegen.py` — `$GOWIN_LD_PRELOAD` override for headless gw_sh.

### Result (M1 validation)
`make apycula/GW1N-2.msgpack.xz` builds a chipdb matching the datasheet
(2304 LUT4 / 4 BSRAM / no DSP / 136 IOB). A real AND-gate bitstream
`gowin_unpack -d GW1N-2`s cleanly, recovering the LUT4 (`INIT=16'ha0a0`) and IO buffers.

### Open items / next (M2+)
- **M2 (next): DFF/LUT config bits.** A FF-less design unpacks with ~1726 spurious
  `DFFSE` — DFF mode/config bit positions need diff-fuzzing to confirm/correct.
- Map the 10 `UNKNOWN_CFG_*` special-pin IO config codes (e.g. code 45 @ IOR3A).
- Parse the partType-1 extended table at `0x7b4a8`; map the OSCO oscillator ports
  and the PLL (M4).
- Run the M0 blinky round-trip through yosys + nextpnr-himbaechel.

### How to reproduce on mars
```bash
cd ~/gw1n2-apicula/tools/apicula && source .venv/bin/activate && source ../gowin-env.sh
make apycula/GW1N-2.msgpack.xz            # build the chipdb
# synth a design for GW1N-UV1P5QN48XFC7/I6 with gw_sh, then:
python3 -m apycula.gowin_unpack -d GW1N-2 <design>.fs -o out.v
```

## 2026-06-13 (cont.) — M2 started: LUT4 truth-table fuses verified ✅

Built a diff-fuzzing harness (`tools/fuzz.py`) and confirmed the GW1N-2 LUT logic
config bits are correct.

- **DFF "noise" is not a bug.** The known-good GW1NZ-1 unpacks a FF-less AND gate with
  862 `DFFSE` (≈ its DFF count); GW1N-2 shows 1726 (≈ its DFF count). `gowin_unpack`
  emits a DFF bel per CLS for *every* device — GW1N-2 decodes identically to a
  supported part. De-risks M2.
- **LUT4 fuses fully mapped & verified** (`tools/m2_lut_full.py`). Single-bit
  diff-fuzzing of a single LUT4 (INIT base 0x6996): each of the 16 INIT bits flips
  **exactly one** bitstream fuse, all in one tile (rows 410–411, cols 76–83), control
  run = 0 diffs (deterministic flow). `gowin_unpack` recovers the exact (physical)
  truth table every time. Recovered INIT differs from the source INIT only by a
  consistent input-pin permutation (PnR assigns a,b,c,d→I0..I3 in a permuted order);
  the logical→physical bit map is a clean bijection — i.e. the LUT bits are read 100%
  correctly. So LUT truth-table support for GW1N-2 is **confirmed**, not just plausible.

### M2 remaining
- DFF config bits (clock enable, set/reset polarity, sync/async) — same diff-fuzz
  method on registered designs. Then M3 routing.

## 2026-06-13 (cont.) — M2 DFF config bits checked ✅ (M2 substantially done)

- **DFF config fuses are present and cleanly locatable by diff-fuzz**
  (`tools/m2_dff.py`). Same single-DFF design, vary one attribute, diff bitstreams:
  - `DFF` vs `DFFN` (clock edge): **exactly 1 fuse** flips, at (398,1).
  - `DFF` vs `DFFC` (async clear): 8 fuses, clustered in the FF tile (rows 394–411).
- **No GW1N-2-specific DFF decode gap.** `gowin_unpack` emits a structural `DFFSE`
  for *every* CLS on GW1N-2 (1728) — but the known-good **GW1NZ-1 does the same**
  (864 `DFFSE`, a `DFFC` design decodes identically). So GW1N-2 DFFs behave exactly
  like the reference device; the DFF primitive support is inherited correctly from the
  shared family code. (`tools/m2_dff_cmp.py`.)
- **M2 status:** LUT4 truth-table fuses fully mapped & verified read-correct; DFF
  config fuses located and confirmed at parity with the reference device. The deepest
  per-mode DFF validation (and a full LUT+DFF *pack→unpack* round-trip) needs the
  gowin_pack/routing side, which comes with **M3 (routing)** — the next milestone.

## 2026-06-13 (cont.) — M3 routing decode validated ✅ (reference parity)

**Key realization:** GW1N-2 routing is **not** a from-scratch fuzz job. The pip
fuse maps come straight from the GW1N-1P5C vendor `.fse` that Apicula's
`fse_pips()`/`fse_clock_pips()` already parse — and they are fully populated in our
chipdb: **97,916 pip dest↔src options + 3,440 clock-pip options** across all 37 tile
types. So M3 = *validate that gowin_unpack decodes that routing correctly*, not
reverse-engineer it.

**Method — route-sensitivity diff-fuzzing** (`tools/m3_routing.py`). A static
connectivity graph can't fully resolve Apicula's netlist because inter-tile wires go
through the node/alias system (a leading backtick, e.g.
`assign R12C2_A0 = `R12C1_E11;`). So instead: keep one LUT4 fixed, move the output
pad to many far pins, and confirm both the bitstream and the decode track the change.

- **Complete inter-tile routes decoded to the correct OBUF.** Of the placements
  whose route is expressible as plain assigns, **5/5 traced routes on GW1N-2 are
  distinct and complete**, each ending at the right output buffer — reaching both the
  north edge (R1) and south edge (R19), e.g. pin 40:
  `R12C2_F0 → W80 → R12C7_E81 → R12C15_N22 → R10C15_N81 → R2C15_N10 → R1C15_B5`.
- **Fuse↔readback fidelity.** Moving the output pad changes **34–64 routing-fuse
  bits**; the **control (same placement synth'd twice) = 0 bits** (deterministic);
  and the decoded route changes correspondingly. So pip read-back tracks the actual
  bitstream.
- **Reference parity.** The known-good **GW1NZ-1** shows the identical mechanism
  (some routes assign-traceable, the rest via node aliases; control = 0). GW1N-2
  routing decode behaves exactly like a supported device.

The "NO PATH" placements are a limitation of the static tracer (the last hop is a
node alias it doesn't resolve), not a GW1N-2 decode defect — they occur identically
on GW1NZ-1.

### M3 status & what's left
- **Routing *read* path validated** for GW1N-2 (inter-tile pips + correct OBUF
  delivery + deterministic fuse mapping, at reference parity).
- Still open (and now mostly *generic* Apicula work, not GW1N-2-specific): the full
  `nextpnr-himbaechel` round-trip (M0 blinky pack→route→bitstream→unpack), which is
  the ultimate end-to-end proof; clock-spine/global routing deep-dive; and the
  earlier deferred items (10 `UNKNOWN_CFG_*` IO codes, OSCO ports, partType-1
  extended table / PLL → M4).

## 2026-06-13 (cont.) — END-TO-END ROUND-TRIP WORKS ✅ (M0 round-trip + stretch goal)

**We authored our own GW1N-2 bitstream and read it back faithfully.** Full chain:
`yosys synth_gowin → nextpnr-himbaechel → apycula gowin_pack → .fs → gowin_unpack`,
all on mars. This is the *write* path, not just unpacking the vendor stream — it
closes the M0 round-trip goal and substantially reaches the project's stretch goal.

### How the nextpnr side was stood up (all on mars, lives outside the apicula repo)
nextpnr-himbaechel loads a per-device `chipdb-<dev>.bin`; oss-cad-suite ships none for
GW1N-2. The himbaechel Gowin chipdb is **generated from our Apicula chipdb** by a
script in the *nextpnr source tree* (not the binary distro). Steps:
1. Cloned `YosysHQ/nextpnr` at the exact commit of the installed binary
   (`32324500`, = `nextpnr-0.10-77-g32324500`) → `tools/nextpnr/`.
2. Built `bbasm` standalone (`g++ -std=c++17 bba/main.cc -lboost_program_options`;
   `apt install libboost-program-options-dev`). cmake isn't on mars — not needed.
3. Patched `himbaechel/uarch/gowin/gowin_arch_gen.py` for GW1N-2
   (`tools/patches/np_gowin_gw1n2.py`, idempotent): (a) skip the PLL bel when absent
   (our chipdb has no `RPLLA` — PLL is in the unparsed partType-1 table, M4); (b) add
   `GW1N-2` to the `simple_io` device set (mirrors GW1NZ-1 / the 1P5 die).
4. `gowin_arch_gen.py -d GW1N-2 -o chipdb-GW1N-2.bba` → `bbasm --le` →
   `chipdb-GW1N-2.bin` (6.65 MB), installed into
   `oss-cad-suite/share/nextpnr/himbaechel/gowin/`.

**Device→family gotcha:** the *compiled* binary's regex maps partnumber
`GW1N-UV1P5…` → family `GW1N-1` (the "1" of "1P5") and would load the wrong chipdb.
Override with **`--vopt family=GW1N-2`** to force our chipdb. The package
(`GW1N-UV1P5QN48XF`) is parsed from the partnumber and matched inside the chipdb.

### Result (`tools/roundtrip/`, design = registered AND `r <= a & b`)
- nextpnr placed+routed cleanly on `chipdb-GW1N-2.bin` (1 benign warning: clock fell
  back from dedicated to general routing).
- `gowin_pack -d GW1N-2` emitted `top.fs` — a **well-formed GW1N-2 bitstream**: sync
  word `0xA5C3`, device-ID command `0x06000000` + IDCODE **`0x0120681B`**.
- `gowin_unpack -d GW1N-2` reads it back with faithful logic:
  - `LUT4 INIT = 0x8888` == `AND(I0,I1)` (a&b),
  - `DFFE.D = LUT.F0` (register captures the AND result), `.CLK = CLK0` (clk),
  - `OBUF` driven (via routing) from the DFF Q → output `q`.
  (The 2nd `DFFE` is the unused CLS half — the same structural-DFF artifact noted in
  M2, not a real cell.)

### Repro on mars
```bash
cd ~/gw1n2-apicula/tools/apicula && source .venv/bin/activate
bash ~/gw1n2-apicula/tools/roundtrip/run.sh   # yosys→nextpnr→pack→unpack
# regenerate the himbaechel chipdb if the apicula chipdb changes:
python3 /tmp/np_gowin_gw1n2.py tools/nextpnr/himbaechel/uarch/gowin/gowin_arch_gen.py
python3 tools/nextpnr/himbaechel/uarch/gowin/gowin_arch_gen.py -d GW1N-2 -o /tmp/chipdb-GW1N-2.bba
tools/nextpnr/bba/bbasm --le /tmp/chipdb-GW1N-2.bba \
  tools/oss-cad-suite/share/nextpnr/himbaechel/gowin/chipdb-GW1N-2.bin
```

### What this does and doesn't prove
- ✅ Logic (LUT), registers (DFF), IO, and inter-tile routing all round-trip through
  both the read and write paths — strong, independent confirmation of M1/M2/M3.
- ⏳ Not yet verified on **physical hardware** (the scope FPGA — Needs David).
- ⏳ PLL / BRAM / DSP not exercised (PLL bel skipped in the generator → M4); clock
  used general routing, not the dedicated global tree (worth a later look).

## 2026-06-13 (cont.) — M4 hard blocks: BRAM decodes ✅, PLL present (portmap partial)

### BRAM (M4b) ✅
BRAM was **already structurally present** in the chipdb — `fse_bram()` is created via
`get_tile_types_by_func(...,'B')` with no device gate, so our GW1N-2 chipdb has the
BSRAM bel (tile type 39) + 8 BSRAM_AUX (40,41,80–85). Validated the *decode*
(`tools/m4_bram.py`): synth a 256×8 single-port RAM with the Gowin oracle →
`gowin_unpack -d GW1N-2` recovers a **`BSRAM` primitive with DO0–DO7 wired to
fabric**. That's the decode M5 (scope bitstream) needs. (Deeper init-content
round-trip is a later follow-up; structural read works.)

### PLL (M4a) — bel + config present, portmap partial
`fse_pll()` had no GW1N-2 case → no RPLLA bel. Added one: **GW1N-2 PLL = tile type
50** (the GW1N-1P5C die; cf. 88 for GW1N-1/GW1NZ-1). With that, the chipdb builds an
`RPLLA` bel with its config fuses.

**But the PLL portmap is a real vendor-data quirk:** for GW1N-1P5C the base-region
`.dat` `PllIn`/`PllOut` are **all -1** (vs GW1NZ-1 where they're populated). The real
PLL wire map lives in the **partType-1 extended table at `0x7b4a8`** — the same place
the GW5A series keeps it (`read_5Astuff`). Confirmed: the extended region (~`RS+0x8a`)
contains the rPLL-family wire-index pattern (`…29,2,6,10,14,18,22,26,30,3,7,11,…`),
matching GW1NZ-1's `PllIn` fingerprint (`tools/m4_pll_scan.py`). Pinning the exact
field offsets reliably needs the EDA oracle (a wrong portmap is worse than none), so:
- Guarded the `-1` entries in `dat_portmap` so the build is robust and RPLLA exists
  with config fuses (PLL is config-decodable; routing partial).
- Full extended-table PLL portmap decode = **M4a follow-up** (located, not finished).

CLKIN maps fine (`PllClkin[1] = (124,0)`), so the dedicated PLL clock input is known.

### Changes (apicula)
- `chipdb.py` `fse_pll()`: GW1N-2 case (ttyp 50 → RPLLA).
- `chipdb.py` `dat_portmap()`: skip `-1` PLL port entries (GW1N-2 base PllIn/PllOut
  are all -1; real map is in the extended table).

### Status vs M4 goal
- BRAM config/decode: ✅ (structural read validated).
- PLL: bel + config ✅; portmap ⏳ (extended-table decode located, follow-up).
- DSP: N/A — GW1N-2 has no DSP.
- This is **enough to attempt M5** (unpack the real scope bitstream) — BRAM and the
  fabric all decode; an incomplete PLL portmap affects PLL *routing* reporting, not
  whether the stream unpacks.

## 2026-06-13 (cont.) — 🎯 M5: THE REAL SCOPE BITSTREAM UNPACKS (project goal)

Unpacked the **stock FNIRSI 2C53T bitstream** (`reference/scope_bitstream_2c53t_v120.bin`,
115638 B, sha256 `5a0e7338…`) into a GW1N-2 fabric netlist. **Project headline goal hit.**

### binary → .fs converter (`tools/bin2fs.py`)
gowin_unpack reads ASCII `.fs`; the scope ships raw `.bin`. A `.fs` is just the
bitstream bytes rendered MSB-first as `0/1` with a newline at every command/frame
boundary (see `bslib.write_bitstream`); the `.bin` is the same bytes with no
newlines. So the converter re-inserts boundaries using the chipdb's command lengths:
- header = the 10 `db.cmd_hdr` commands (lengths 20,2,2,8,8,8,4,8,4,4 = **68 B**),
- **722 frames × 160 B** each (152 data + 2 CRC + 6×0xff pad) = 115520 B,
- footer = the 6 `db.cmd_ftr` commands (= **50 B**).
68 + 115520 + 50 = **115638 = file size, exactly.** Frame count (722) is read from
the `3b8002d2` command; the stream is uncompressed (0x10 bit 13 clear).

### Validation — clean unpack + plausibility ✅
`gowin_unpack -d GW1N-2 scope.fs` exits 0. **Every per-frame CRC-16 assert passes**,
which independently proves the conversion is byte-correct. The recovered netlist
(`tools/m5/scope_unpacked.v`, 2.18 MB) is unmistakably the real scope design:
- **847 LUT4** (real INITs: 00ff, ff00, …), **879 real DFFs** (DFFE/DFFCE/DFFRE/DFFPE),
- **192 ALU** (arithmetic — sample counters/accumulators),
- **4 BSRAM** — *exactly* the GW1N-2's 4 block RAMs, all used (sample buffers; M4 decode),
- **15 IDDRC + 1 ODDRC + DLCE/DLE** — DDR I/O + delay cells (the high-speed ADC front-end),
- **2 RAM16SDP4** distributed RAM, **59 IO buffers**, **37,226 routing assigns**, 1047 defparams.
(493 `DFFSE` are the known structural-DFF artifact, not real cells.)

### The one caveat — PLL (expected)
The scope **uses the PLL** (unpack prints `Unknown attr name for table: PLL
code:107/108` — real PLL config fuses are set), but it isn't emitted as a full
`RPLLA` instance because GW1N-2 PLL support is partial (portmap + attr codes
107/108 live in the partType-1 extended table — the **M4a follow-up**). Everything
else decodes cleanly; the PLL gap does not block the unpack.

### Repro (on mars)
```bash
cd ~/gw1n2-apicula/tools/apicula && source .venv/bin/activate
python3 ~/gw1n2-apicula/tools/bin2fs.py ~/m5/scope_bitstream_2c53t_v120.bin ~/m5/scope.fs -d GW1N-2
python3 -m apycula.gowin_unpack -d GW1N-2 ~/m5/scope.fs -o ~/m5/scope_unpacked.v
```

## 2026-06-13 (cont.) — M4a PLL located + M6 contribution prepped

### M4a PLL — both sub-problems located (need the EDA oracle to finalize)
Tried to finish PLL support. Found the GW1N-2 PLL = **tile type 50** and added the
`fse_pll` case + RPLLA bel. But two real gaps remain, both now precisely located:
1. **Portmap**: GW1N-1P5C's base `.dat` PllIn/PllOut are all -1; the real map is in
   the partType-1 extended table at `0x7b4a8`. Dumped it (`tools/m4_pll_dump.py`):
   `PllIn[0:18]` at `RS+0x0` matches GW1NZ-1 **exactly**; `PllOut` values (34,39,36,
   37,38) at `RS+0xc8`. It's the **GW5A-style expanded layout** (cf.
   `dat_parser.read_5Astuff`) relocated to the table head — not the simple base block.
   Pinning exact field boundaries needs the oracle (synth an rPLL, check wire usage).
2. **Attr codes**: the M5 scope unpack warns `Unknown attr name for table: PLL
   code:107/108` — `gowin_unpack.get_attr_name()` can't find those in the `attrids`
   PLL table. Needs mapping.
Kept the build robust (RPLLA bel + config; `-1` guard in `dat_portmap`). Neither gap
blocks M5. Tracked as the M4a follow-up.

### M6 — contribution prepared (submission is David's)
Consolidated **all** M1–M5 apicula changes into one reviewable diff:
`tools/patches/gw1n2-support.patch` (7 files: bslib, chipdb, chipdb_builder,
dat_parser, gowin_unpack, codegen, Makefile; ~65 insertions) + the nextpnr-side
`tools/patches/nextpnr-gw1n2-gen.patch`. Wrote a staged-PR plan
(`docs/04-contributing.md` → "GW1N-2 staging plan"): PR1 partType-1 `.dat` (most
valuable standalone — unblocks the whole 1P5/2/2B family), PR2 device recognition +
chipdb build, PR3 pinout/IO/OSC, PR4 PLL (hold until M4a done), plus the nextpnr
repo changes (CMakeLists device list + `gowin.cc` family regex). Refreshed
`docs/05-needs-david.md`: build blockers resolved; only PR submission + optional
hardware verification remain human-only.

## 2026-06-13 (cont.) — M4a PLL: thoroughly investigated → blocked on environment

Attempted full PLL decode. Hit a genuine hard wall and reverted to the clean M4
checkpoint (net code change = 0). The findings, so the next person doesn't re-tread:

1. **No write-path oracle.** Gowin EDA refuses to synthesize an rPLL for the only
   license-free GW1N-2 proxy: `ERROR (EX0312): There is no rPLL resource in current
   device` for `GW1N-1P5C`. So we cannot generate a known-good PLL bitstream to
   validate any portmap/location/attr hypothesis.
2. **The one real sample (scope) doesn't help enough.** GW1N-2's PLL bel resolves to
   grid `(0,0)` (ttyp 50), but the scope's PLL clock rides `TRPLL0CLK*` spine wires
   (named for top-right), and the `(0,0)` tile in the scope carries only PLL
   calibration bits (attr codes **107/108** — internal regulator trims, sitting
   between `PLLREG0`=106 and `A_IDIV_SEL`=109 in `attrids.pll_attrids`). No active
   rPLL instance emits there.
3. **Portmap located, not cracked.** Base `.dat` PllIn/PllOut are all -1; the real
   map is in the partType-1 extended table at `0x7b4a8`, in the **GW5A-style expanded
   layout** (PllIn[0:18] at `RS+0x0` byte-matches GW1NZ-1; PllOut values at `RS+0xc8`).
   Tools: `m4_pll_dump.py`, `m4_pll_fp.py`, `m4_pll_oracle.py`.

Tried reusing GW1NZ-1's portmap + a derived `_pll_loc` — but with no oracle and no
instance emitting, that's shipping unvalidated guesses, so it was reverted.

**Conclusion:** full PLL support needs **real GW1N-2 vendor data (Standard-edition
license)** or multi-bitstream RE — it is *not* completable with the Education proxy.
It does **not** block M5 (the scope unpacks cleanly; the PLL is the one unmodeled
block). Code remains at the M4 checkpoint: RPLLA bel + config present, portmap
deferred, build robust.

## 2026-06-13 (cont.) — M6 turnkey: staged PRs + validated example

Made the upstream contribution submission-ready (submission itself stays David's):
- **Split** the consolidated diff into staged per-PR patches in
  `tools/patches/staged/` — PR1 partType-1 `.dat`, PR2 recognize+build, PR3
  pinout/IO/OSC. The blocked rPLL hunks and the local `codegen.py` aid are split out
  (`HELD-*`, `LOCAL-*`) and excluded from submission.
- **Validated the contribution set**: applying PR1+PR2+PR3 to a *clean* apicula tree
  builds the GW1N-2 chipdb and unpacks the real scope bitstream cleanly (847 LUT4 /
  879 FF / 192 ALU / 4 BSRAM), with no PLL — proving the split is self-consistent.
- **PR text + tracking issue** drafted ready-to-paste in `docs/08-pr-drafts.md`.
- **Validated blinky example** (`tools/roundtrip/gw1n2-example/`): a counter→LED that
  round-trips yosys→nextpnr→gowin_pack→unpack on GW1N-2 (readback = 26 ALU + 34 DFFE
  + LED OBUF). Seed for upstream `examples/gw1n2/`; add with/after the nextpnr PR
  (CI builds examples through nextpnr).

## 2026-06-13 (cont.) — nextpnr PR finalized + CI-equivalent from-source validation

Turned the mars nextpnr setup into a clean, submission-ready nextpnr PR and proved
it the way `toolchain.yml` would:
- **Simplified the nextpnr change to 2 files** (`tools/patches/staged/nextpnr/01-gw1n2-arch-gen.patch`):
  `CMakeLists.txt` (add `GW1N-2` to `ALL_HIMBAECHEL_GOWIN_DEVICES`) +
  `gowin_arch_gen.py` (simple_io set + PLL-skip when `RPLLA` absent).
- **Dropped the `gowin.cc` family-regex change** — it was never needed. The examples
  Makefile passes `--vopt family=` idiomatically (`tangnano9k`→`GW1N-9C`,
  `tangnano20k`→`GW2A-18C`), so the GW1N-2 example uses `--vopt family=GW1N-2`. This
  also avoids a hacky `GW1N-UV1P5…`→GW1N-2 mapping. Corrected `docs/04`/`docs/08`.
- **From-source CI-equivalent build (mars):** installed cmake/eigen/boost; built
  nextpnr from commit `32324500` with `-DHIMBAECHEL_GOWIN_DEVICES="GW1N-2"` and
  `APYCULA_INSTALL_PREFIX=<apicula>/.venv`. The CMake `foreach` ran
  `gowin_arch_gen.py -d GW1N-2`, produced `chipdb-GW1N-2.bba`/`.bin`, and compiled the
  binary with **0 errors**. (GW1N-1 in the same list only failed because our apicula
  tree never built `GW1N-1.msgpack.xz` — devices build independently, so GW1N-2-only
  is a faithful per-device test.)
- **Example as a self-contained subdir** mirroring `examples/gw5a/`:
  `tools/patches/staged/examples-gw1n2/` (blinky.v counter→LED, gw1n2.cst, Makefile,
  README). `make gw1n2 NEXTPNR=<built binary>`: yosys → nextpnr (`--vopt family=GW1N-2`,
  0 errors) → `gowin_pack` → `blinky-gw1n2.fs` with sync `0xA5C3`; `gowin_unpack`
  reads it back to 26 ALU / 38 DFFE / 8 LUT4 / OBUF+IBUF.
- **Open maintainer item:** board/part identity (no standard GW1N-2 dev board; die is
  GW1N-1P5C-branded). Example uses partnumber `GW1N-UV1P5QN48XFC7/I6`; CI-valid as-is.
  nextpnr PR text ready in `docs/08`.

## 2026-06-13 — R3 (osc collab): capture-arming netlist trace
- Answered the osc side's ⭐ R3 ("what arms/sustains scope capture") by static-tracing
  the unpacked stock netlist. Tool: `tools/m_arming.py`. Findings doc:
  `docs/R3-CAPTURE-ARMING-FINDINGS.md`.
- Key results: all 4 sample BRAMs are permanently write-enabled (`WREA=VCC`); capture is
  gated by `CEA` = a pure function of an internal ~383-DFF free-running address/state
  counter (CH1 gate `INIT=0x3300` = `qC & ~qB`); sample clock is on the global/PLL spine
  (no MCU pin). The capture engine's master **run/re-arm** control is the pad at apicula
  loc **IOR1B** (QFN48-proxy pin 35): 70 DFF.CE + 8 DFF.SET + 156 DFF.D. Secondary
  controls: IOB7B (pin 19, GCLKC_4) and a bit on **SI** (IOB18B, pin 24).
- Identified the runtime control bus as the **reused SSPI pins**: SCLK=IOB5A(16),
  SI=IOB18B(24), SO=IOB5B(17, the `0x04`/`0x05` readback IOBUF), CS_N=IOB18A(23). This is
  the osc "SPI3" bus; one control-register bit feeds the capture-enable path.
- Caveats recorded: static (not simulated); pin numbers are GW1N-1P5C/QFN48XF proxy
  (IOB names + special-fns are the package-independent truth); many top-edge IOT pads
  unbonded on QFN48. Bonus cross-check: JTAG is at IOT7/IOT9 (proxy pins 44/45/47/48),
  NOT QN48 pins 8–11 (those are left-edge GPIO) — flagged for maksidze's gold-pad trace.
- Read-side (B-port) follow-up: BRAMs are true dual-port (A=ADC write, B=MCU read);
  all 4 channels' read data mux onto SO (IOB5B/pin17, only IOBUF), opcode-selected via SI,
  control-driven OEN. Read pointer is from the same ~383-DFF control cone → word↔byte
  mapping not statically derivable; R1 ramp validator is the right tool. Findings appended
  to `docs/R3-CAPTURE-ARMING-FINDINGS.md` and copied into osc repo as new file
  `docs/R3_CAPTURE_ARMING_FROM_APICULA.md` (uncommitted).
- R3 follow-up #2 (osc §4/§5): re-arm logic solved. Re-arm = single AND gate
  R6C16_LUT4_7 (INIT=0x8000) requiring IOR1B (run) ∧ IOB7B (enable) ∧ SPI-control-bit
  (flop D<-SI) coincident — so IOR1B/PB11 alone can't re-arm (explains the bench). Async
  SET = level arm. Data-ready (PC0) candidate = IOR13A (registered, counter/BRAM cone).
  IOB7B = held-high co-enable (PC6/PC11). §5: apicula GW1N-2 AND GW1N-1P5C both use
  QFN48XF with JTAG at top-edge pins 44-48 — disagrees with osc's UG171E QN48 (8-11), so
  package numbering differs; suggested deriving the offset from the confirmed SPI anchors.
  Tool: tools/m_rearm.py. Reply: docs/R3_FOLLOWUP2_FROM_APICULA.md (+ copied to osc, uncommitted).
- R1 scope-readout VALIDATOR built (osc request) — tools/r1_build_validator.py.
  Discovered stock bitstream = 466 main + 256 BRAM-init frames = 722, and the init region
  is ALL ZERO. Patched ONLY the init region: BSRAM_0(R10C2/CH1)=byte ramp (A&0xFF, wraps at
  256), BSRAM_3(R10C17/CH2)=A5/5A walking marker; BSRAM_1/2 left zero. Used apicula's
  store_bsram_init_val encoder + a new inverse decoder (round-trip verified), grafted into
  stock bs and re-emitted via bslib.write_bitstream (CRCs auto). VERIFIED: main
  logic/routing region = 0 differing bits vs stock (readout path byte-identical), only init
  changed, hdr/ftr identical, frame CRCs pass, CH1/CH2 decode back to ramp/marker.
  Artifact: tools/r1/scope_R1_validator.fs (925842 B, sha256 3f24bd07...). Also serves as
  R2 (load-path proof). Survives until capture armed (CEA=qC&~qB=0 at reset). Doc:
  docs/R1_VALIDATOR_FROM_APICULA.md. Staged in osc: fpga_bitstream/scope_R1_validator.fs +
  docs/R1_VALIDATOR_FROM_APICULA.md (uncommitted). SAFETY: SRAM load only (openFPGALoader -m).

## 2026-06-13 — osc config-entry questions (CONFIG_ENTRY_PROOF_FROM_OSC.md)
- Answered all 4, grounded in UG290-2.9E + stock-header decode. Reply:
  docs/CONFIG_ENTRY_REPLY_FROM_APICULA.md (copied to osc, uncommitted).
- Key correction: FLASH_LOCK (status bit 17) is flash READBACK protection only (UG290 Tbl
  7-12 note [2]: "Flash cannot be read back but can still be erased") — it does NOT block
  SRAM reconfig. Not the blocker.
- Stock header decoded: 0x10 CONFIG_MODE word = all-zero (no security/encrypt/lock in the
  scope SRAM image); IDCODE 0120681B; 3b8002d2 = 722 frames. Status Security Final(bit14)=0.
- Real blocker: a running auto-booted device needs RECONFIG_N pulse / power-cycle / cold-boot
  window to re-enter config; SSPI 0x15 alone is ignored (Edit Mode bit7 stays 0). Documented
  reconfig flow needs erase-then-write (0x15/0x05/.../0x09/0x3A then 0x15/0x12/0x17/.../0x3A).
- Q3 confirmed: JTAG SRAM config is universal, MODE-independent, independent of FLASH_LOCK
  ("writes bitstream to SRAM... All Gowin FPGA products support JTAG config mode"); status
  bit10 Non-jtag active=0 → JTAG enabled. JTAG -m is the clean route; first test
  openFPGALoader --detect for IDCODE. SAFETY: -m only, never flash (JTAG can write flash too).
- Q4: R1 validator already built/staged.

## 2026-06-13 — Upstream PRs OPENED (yrabbit nod on #515: "Looks quite acceptable to me:)")
- Forked YosysHQ/apicula + YosysHQ/nextpnr to DavidClawson. All patches applied CLEAN to
  current upstream (no --3way needed). Clones in ~/gh-prs/.
- apicula (base master): #516 dat_parser partType-1 (standalone) → #517 recognize+build
  (dep #516) → #518 pinout/IO/OSC (dep #517). Stacked; all OPEN+MERGEABLE.
- nextpnr (base main, note: nextpnr default branch is `main` not `master`): #1735
  [himbaechel/gowin] Add GW1N-2 device. OPEN+MERGEABLE.
- Posted coordinating comment on #515 (issuecomment-4700047247) listing PRs + merge order.
- HELD per RUNBOOK step 6: examples/gw1n2/ blinky + toolchain.yml matrix entry — send only
  after nextpnr#1735 merges and apicula bumps its pinned nextpnr commit (else example CI red).

## 2026-06-13 — BSRAM init-content decoder (candidate upstream contribution)
- tools/bsram_init_decode.py: inverts gowin_pack.store_bsram_init_val to recover BSRAM
  memory contents from a bitstream's appended init region. Unified bit-map shared by
  encode/decode (exact inverses by construction). Self-test round-trips BOTH width modes
  (256 / 288=X9) against apicula's real encoder: OK.
- End-to-end verified: extracts R1 validator → R10C2=ramp(00..0f), R10C17=A5/5A, others 0;
  stock scope → all-zero (init region empty); authored 288-mode design → data recovered.
- KNOWN ROUGH EDGE: the 288/X9 BYTE-view has a parity-placement off-by-one (byte1 shifted);
  canonical INIT_RAM bitstrings are correct (round-trip), only the ×18 byte grouping needs
  the ECC-bit position pinned. 256-mode (scope/R1) byte-view is exact.
- INTEGRATION FINDING: a clean gowin_unpack *core* feature (emit INIT_RAM per BSRAM) also
  needs BSRAM width/subtype config-decode — gowin_unpack currently recovers only CSA/SPA
  bel attrs, not BIT_WIDTH/SUBTYPE. So full integration is a medium task, not a quick win.
  Recommend floating to yrabbit (want it? as gowin_unpack feature vs standalone tool?)
  before building a speculative PR. Decoder core is done + the tool already re-verified R1.

## 2026-06-13 — PR review round 1 (yrabbit)
- **PR1 #516 MERGED.** PR2 #517 got a yrabbit review comment questioning the GW1N-2 GSR
  location (we'd inherited db[0,0]/'C4' from the GW1N-1 group without verifying).
- VERIFIED via Gowin oracle diff-fuzz (tools, fuzz.py): synth a `GSR gsr(.GSRI(rstn))`
  design for GW1N-UV1P5 vs no-GSR baseline. Pin-invariance (reset on pin 35 vs 28,
  intersect changed tiles) isolates the GSR cell = **db[0,1] (R1C2)** — db[0,0] never
  changes. Pip-fuse match: the reset terminates on wire **C4** at db[0,1]. So GW1N-2 GSR =
  db[0,1]/'C4', NOT db[0,0]. yrabbit was right.
- FIX: split GW1N-2 out of the GW1N-1 GSR group into its own elif (db[0,1]/'C4') in
  chipdb_builder.py. Rebuilt GW1N-2 chipdb on mars → confirmed db[0,1] has GSR, db[0,0]
  doesn't. Rebased PR2 onto merged master (#516), pushed fix; rebased/recreated PR3 on top.
  Replied to yrabbit on #517 (issuecomment-4700132734) with the evidence. Staged patches
  02/03 regenerated to match. All three apicula PRs OPEN+MERGEABLE.

## 2026-06-13 — Backlog A2: special-pin IO config codes mapped (UNKNOWN_CFG 10→5)
Resolved half of the GW1N-2 `UNKNOWN_CFG_<n>` placeholders **without the oracle or
fuzzing** — by cross-referencing vendor data. Full write-up:
`docs/IO-CFG-CODES-FINDINGS.md`. Tool: `tools/m_iocfg_mine.py`.
- **Insight:** `_io_cfg` is a single *global* dict for all non-GW5 devices ⇒ Gowin uses
  one consistent `cfg_code` enumeration. A code unlabelled on GW1N-2's QFN48XF is often
  bonded+labelled on a bigger package of another device.
- **Method:** monkeypatch `dat_fill_io_cfgs` (abort the slow build tail with a sentinel),
  record `(device,pin,cfg_code,package_label)` across the 5 minable non-GW5 devices
  (GW1N-2, GW1NZ-1, GW1NS-4, GW1N-9C, GW2A-18C), invert to `code→label`. **Validated:
  reproduces the known `_io_cfg` with 27 agree / 0 contradict.**
- **Resolved 5** (added to `_io_cfg`, each confirmed at a labelled pin on 2 devices):
  `75`→LPLL_T_IN (IOL5A), `136`→MCLK/D4 (IOR6B), `153`→MO/D6 (IOR5B), `154`→MI/D7
  (IOR5A), `160`→MCS_N/D5 (IOR6A). = the MSPI quartet + parallel-config D4–D7 + a PLL
  input. (Bonus: the probe also maps JTAG TCK/TMS/TDO/TDI to IOT9/IOT7 — corroborates R3.)
- **5 stragglers** (43/44/45/46 @ IOR3A/B,IOR4A/B; 141 @ IOB12A): no package label on any
  available device, not in iotable CSVs / binary `.ini`. Kept as honest non-fatal
  `UNKNOWN_CFG` (per "wrong map worse than none"). All unbonded on QFN48XF — hypothesis:
  43–46 may be RPLL dedicated pins of the 1P5/2 die. Would need the datasheet pin table.
- **No regression:** GW1N-2 rebuild now emits 5 (was 10) warnings; the scope bitstream
  unpacks identically (847 LUT4 / 192 ALU / 4 BSRAM / 15 IDDRC / 1 ODDRC). Folded into
  **PR3 (#518)** as a new local commit on `gw1n2-io` (NOT pushed — David's call); staged
  patch `03-pinout-io-osc.patch`, consolidated `gw1n2-support.patch`, and `pr3-io.md`
  regenerated to match.
