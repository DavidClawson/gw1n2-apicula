# 08 — Upstream PR drafts (ready to paste)

> Turnkey text for submitting GW1N-2 support to Apicula. Patches live in
> `tools/patches/staged/`. Submission order is smallest/most-independent first.
> Validated 2026-06-13: PR1+PR2+PR3 applied to a clean apicula tree build the
> GW1N-2 chipdb and unpack the real FNIRSI scope bitstream cleanly (no PLL needed).
>
> The PLL is intentionally **excluded** (blocked on real GW1N-2 vendor data — see
> `docs/07`/`docs/06`); `HELD-pll-partial.diff` and `LOCAL-codegen-preload.patch`
> are NOT for submission.

## Step 0 — coordinate first
Post in Matrix `#apicula:matrix.org` (ping `yrabbit`) and open the tracking Issue
below before opening PRs. Confirm nobody else is mid-flight on GW1N-2 and that the
staging is agreeable.

### Tracking Issue — "Add GW1N-2 support"
> **Add Gowin GW1N-2 (IDCODE 0x0120681B) support**
>
> I'd like to contribute support for the GW1N-2 (GW1N-UV2 family; 2304 LUT4, 4 BSRAM,
> 1 rPLL, no DSP). It's the FPGA in the FNIRSI 2C53T scope. I have it building and
> unpacking the device's real stock bitstream cleanly.
>
> Two things worth flagging up front:
> 1. The GW1N-2 die ships license-free in the Education edition only as **GW1N-1P5C**
>    (same silicon — verified the synth emits IDCODE 0x0120681B). So the device uses
>    GW1N-1P5C vendor data.
> 2. The real reason it was never finished: GW1N-2's `.dat` is **partType 1**, which
>    `dat_parser` rejects. partType-1 files are identical to partType-0 in the parsed
>    fixed-offset region and only append an extended table at 0x7b4a8.
>
> Plan: stage as small PRs — (1) partType-1 `.dat` support, (2) device recognition +
> chipdb build, (3) pinout/IO/OSC. Validated end-to-end on the stock 2C53T bitstream
> (847 LUT4 / 879 FF / 192 ALU / 4 BSRAM / DDR I/O all decode).
>
> Known gaps deferred to follow-ups: the rPLL (its portmap is in the partType-1
> extended table; can't be validated because GW1N-1P5C exposes no rPLL synthesis
> resource in Gowin EDA — needs real GW1N-2 vendor data), and ~10 special-pin IO
> config codes. Neither blocks unpacking.

---

## PR 1 — `dat_parser: support partType-1 .dat files`
**Patch:** `staged/01-dat_parser-parttype1.patch` · **Files:** `apycula/dat_parser.py`

> Gowin's `.dat` files carry a `partType` field (offset 0x7b4a4). `dat_parser`
> handles partType 0 (1/2 series) and 2 (5 series) but raises on **partType 1**, the
> format used by the GW1N-2 / GW1N-1P5 / GW1N-2B / GW1NR-2 / GW1NZR-2 family.
>
> partType-1 files are byte-identical to partType-0 across the entire fixed-offset
> region the parser reads (primitives, grid, portmap, IO) — they only *append* a
> ~33 KB extended table at 0x7b4a8. This patch treats partType 1 like partType 0 (all
> existing offset asserts pass) and reads the trailing table. This alone unblocks the
> whole GW1N-2/1P5 family for downstream device work.

**Standalone** — no new device required to land it; it's a parser fix.

## PR 2 — `GW1N-2. Recognize device + build chipdb`
**Patch:** `staged/02-recognize-and-build.patch` ·
**Files:** `apycula/bslib.py`, `apycula/chipdb_builder.py`, `apycula/gowin_unpack.py`, `Makefile`
**Depends on:** PR 1

> Adds the GW1N-2 device:
> - `bslib.py`: recognize IDCODE `0x0120681B`.
> - `chipdb_builder.py`: `DEVICE_PARAMS['GW1N-2']` (vendor device `GW1N-1P5C`, package
>   `QFN48XF`, partnumber `GW1N-UV1P5QN48XFC7/I6`), `_chip_id`, GSR, Makefile target.
> - `gowin_unpack.py`: package mapping.
>
> `make apycula/GW1N-2.msgpack.xz` then builds a chipdb matching the datasheet
> (19×20 grid, 2304 LUT4, 4 BSRAM, no DSP, 136 IOB).

## PR 3 — `GW1N-2. Pinout, IO config, OSC`
**Patch:** `staged/03-pinout-io-osc.patch` · **Files:** `apycula/chipdb.py`
**Depends on:** PR 2

> - `json_pinout` / `get_pins`: expose the GW1N-1P5C pinout, keyed under both the
>   vendor name and `GW1N-2`.
> - OSC: an `('OSCO','GW1N-2')` stub so the oscillator hard-block doesn't block the
>   build (full OSCO port map is a TODO).
> - IO config: make an unrecognised special-pin config code non-fatal for GW1N-2
>   (recorded as `UNKNOWN_CFG_<n>`) instead of aborting — ~10 such codes remain to be
>   mapped; flagged as a follow-up.
>
> **Validation (all three PRs):** the real FNIRSI 2C53T stock bitstream
> `gowin_unpack -d GW1N-2`s cleanly — 847 LUT4, 879 FF, 192 ALU, 4 BSRAM, DDR I/O.

---

## Separate repo — YosysHQ/nextpnr (reviewer `gatecat`)
**Patch:** `tools/patches/staged/nextpnr/01-gw1n2-arch-gen.patch` — the **whole**
nextpnr change, only 2 files:
- `himbaechel/uarch/gowin/CMakeLists.txt`: add `GW1N-2` to
  `ALL_HIMBAECHEL_GOWIN_DEVICES` (so the build generates `chipdb-GW1N-2.bin`);
- `himbaechel/uarch/gowin/gowin_arch_gen.py`: add GW1N-2 to the `simple_io` set +
  emit the PLL tile without a PLL bel when the chipdb has no `RPLLA` (PLL-skip;
  drop once apicula's rPLL lands).

**No `gowin.cc` change** (corrected 2026-06-13). The examples Makefile passes
`--vopt family=` as the house idiom (`tangnano9k` → `GW1N-9C`,
`tangnano20k` → `GW2A-18C`); the GW1N-2 example uses `--vopt family=GW1N-2`, so the
"`GW1N-UV1P5…` misparses to GW1N-1" issue never arises and no parser hack is needed.

**VALIDATED end-to-end (2026-06-13, from-source CI-equivalent build on mars):**
- `cmake -DHIMBAECHEL_GOWIN_DEVICES="GW1N-2"` + `make` → ran `gowin_arch_gen.py -d
  GW1N-2` and built `chipdb-GW1N-2.bba`/`.bin`, then compiled the binary, **0 errors**
  (apycula located via `APYCULA_INSTALL_PREFIX=<apicula>/.venv`).
- `make -C examples/gw1n2 gw1n2 NEXTPNR=<built binary>`:
  yosys → nextpnr-himbaechel (`--vopt family=GW1N-2`, 0 errors) → `gowin_pack`
  produced `blinky-gw1n2.fs` (sync word `0xA5C3` correct); `gowin_unpack` reads it
  back to a sensible netlist (26 ALU / 38 DFFE / 8 LUT4 / OBUF+IBUF).

## examples/gw1n2 (CI) — `tools/patches/staged/examples-gw1n2/`
Self-contained example subdir mirroring `examples/gw5a/` (a 24-bit counter→LED
blinky + `gw1n2.cst` + Makefile). `toolchain.yml` runs `examples/` through
nextpnr-himbaechel, which needs the GW1N-2 chipdb, so add this **with** the nextpnr
support (and add a `{target: gw1n2, dir: examples/gw1n2}` matrix entry).

**One open item for the maintainers:** the board/part identity. The only GW1N-2
hardware on hand is the FNIRSI 2C53T scope (not a general dev board), and the die
ships license-free only as GW1N-1P5C, so the example uses the GW1N-1P5C partnumber
`GW1N-UV1P5QN48XFC7/I6`. The example is CI-valid as-is; the board *name* and whether
to brand the part as a real GW1N-2 partnumber (which would need GW1N-2 package
aliases in apicula's pinout data) is the thing to agree with `gatecat`/`yrabbit`.

---

## nextpnr PR — ready-to-paste text

> **Title:** `[himbaechel/gowin] Add GW1N-2 device`
>
> Adds the Gowin GW1N-2 to the Himbächel-Gowin uarch. Pairs with apicula GW1N-2
> support (YosysHQ/apicula — partType-1 `.dat`, device recognition, pinout/IO).
>
> - `CMakeLists.txt`: add `GW1N-2` to `ALL_HIMBAECHEL_GOWIN_DEVICES` so the build
>   generates `chipdb-GW1N-2.bin`.
> - `gowin_arch_gen.py`: add `GW1N-2` to the `simple_io` set (GW1N-1P5C die shares
>   the small-part IO layout with GW1NZ-1/GW1N-1); and in `create_pll_tiletype`,
>   emit the PLL tile without a PLL bel when the chipdb has no `RPLLA`. The GW1N-2
>   rPLL isn't decoded yet on the apicula side (its portmap lives in the partType-1
>   extended table; the license-free GW1N-1P5C proxy exposes no rPLL synthesis
>   resource to fuzz against), so the chipdb has no PLL bel for now — this keeps
>   logic/routing/IO designs building. To be removed once apicula's rPLL lands.
>
> No `gowin.cc` change: the GW1N-1P5C partnumber is selected with
> `--vopt family=GW1N-2`, the same idiom the examples already use for GW1N-9C/GW2A.
>
> Example in apicula `examples/gw1n2/` (blinky); CI `toolchain.yml` matrix gets a
> `{target: gw1n2, dir: examples/gw1n2}` entry. Built and round-tripped a blinky
> through a from-source build with `-DHIMBAECHEL_GOWIN_DEVICES="GW1N-2"`.
>
> **Note on the device/part:** the GW1N-2 die ships license-free only as GW1N-1P5C,
> so the device data and example partnumber are GW1N-1P5C. Open to guidance on the
> preferred device/package naming.
