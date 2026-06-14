# 03 — Work plan & milestones

A milestone is "done" only when its **validation** passes, not when the code runs.

## M0 — Environment proven (gate) ✅ (2026-06-13)
- [x] Gowin EDA Education (V1.9.11.03) installed on mars, headless `gw_sh` synth/PnR
      confirmed working (`QT_QPA_PLATFORM=offscreen` + system-libfreetype preload).
- [x] Apicula cloned, editable-installed, pointed at `$GOWINHOME`.
- [x] OSS-CAD-Suite (yosys + nextpnr-himbaechel) downloaded to `tools/oss-cad-suite`.
- [x] **Rebuilt the GW1NZ-1 chipdb from scratch** — 34/36 Device fields byte-identical
      to the official PyPI build (only `packages`/`pinout` differ; grid 11×20 matches).
- [x] blinky-equivalent round-trip through yosys+nextpnr-himbaechel+gowin_pack done
      (registered AND; see the 2026-06-13 round-trip log + `tools/roundtrip/`).
- **Validation:** existing-device build reproduced ✅. Round-trip ✅ (authored a
      well-formed GW1N-2 `.fs`, IDCODE `0x0120681B`, LUT/DFF/IO/routing read back faithfully).

## M1 — GW1N-2 recognized + grid/IO mapped ✅ (2026-06-13)
- [x] Added GW1N-2 IDCODE `0x0120681B` to `bslib.py` + `_chip_id` + `DEVICE_PARAMS`
      (vendor data = GW1N-1P5C, the same die; verified synth emits `0x0120681B`).
- [x] `fse_parser`/`chipdb_builder` emit a **GW1N-2 grid**: 19×20, **2304 LUT4**,
      1728 DFF, **4 BSRAM**, **no DSP**, 136 IOB, 6 banks — matches the datasheet.
- [x] IO tiles + pin assignments mapped (pinout under GW1N-1P5C/GW1N-2, QFN48XF).
- [x] Key blocker solved: GW1N-2 `.dat` is **partType 1** (unimplemented upstream) —
      RE'd as "partType-0 layout + appended extended table"; treat-as-0 parses cleanly.
- **Validation:** a real GW1N-2 bitstream (AND gate) `gowin_unpack -d GW1N-2`s cleanly
      — recovers the LUT4 (`INIT=16'ha0a0`) + IO buffers. (Per-frame CRC validates.)
- **Deferred to later milestones (stubbed, don't block M1):** OSCO oscillator port
      map (`('OSCO','GW1N-2')` empty stub → M4); 10 special-pin IO cfg codes recorded
      as `UNKNOWN_CFG_*` → map later; the partType-1 extended table at `0x7b4a8`
      (likely PLL/special data) not yet parsed → M4. The ~1726 spurious `DFFSE` in a
      FF-less design show DFF config-bit fidelity is M2 work.

## M2 — Logic primitives mapped ✅ (2026-06-13)
- [x] LUT4 truth-table bit positions confirmed across the grid (all 16 INIT fuses,
      verified read-correct, clean bijection — `tools/m2_lut_full.py`).
- [x] DFF config bits mapped (clock-edge = 1 fuse @ (398,1); async-clear = 8 fuses;
      reference-parity with GW1NZ-1 — `tools/m2_dff.py`).
- **Validation:** LUT read-back bit-exact; DFF fuses isolated. Full LUT+DFF
  pack→unpack round-trip deferred to the packer side (M3/round-trip).

## M3 — Routing mapped ✅ read path (2026-06-13)
- [x] Routing-mux config bits present & decoded over the GW1N-2 grid (97,916 pip +
      3,440 clock-pip options from vendor `.fse`; validated by route-sensitivity
      diff-fuzzing — `tools/m3_routing.py`).
- **Validation:** multi-tile routes recovered correctly on unpack (5/5 distinct
  inter-tile routes traced to the correct OBUF; routing fuses change 34–64 bits with
  placement, control = 0; reference-parity with GW1NZ-1). ✅
- [x] Full `nextpnr-himbaechel` round-trip done — the ultimate end-to-end proof:
      our `chipdb-GW1N-2.bin` places+routes a registered AND, packs to a valid `.fs`,
      and unpacks faithfully (see 2026-06-13 round-trip log). ✅
- [ ] Remaining: clock-spine/global routing deep-dive (clk used general routing).

## M4 — Hard blocks mapped 🟡 (2026-06-13)
- [x] BRAM: BSRAM bel present (no device gate) + **decode validated** — a 256×8 RAM
      synth'd by the oracle unpacks as a `BSRAM` with DO0–DO7 wired (`tools/m4_bram.py`).
- [x] PLL config bits: `RPLLA` bel + config in chipdb (GW1N-2 PLL = tile type 50).
- [~] PLL full decode: **BLOCKED on environment** (investigated 2026-06-13). The
      license-free GW1N-1P5C proxy has *no rPLL synthesis resource* (no write oracle),
      and the scope's PLL tile holds only calibration bits — so the portmap (located
      in the partType-1 extended table @ `0x7b4a8`) and attr codes 107/108 can't be
      validated. Needs real GW1N-2 vendor data / Standard-edition license. DSP: N/A.
- **Validation:** BRAM decodes ✅. BRAM init-content + PLL round-trip = follow-ups.
      Enough to attempt M5.

## M5 — Unpack the real target (project success) ✅ (2026-06-13)
- [x] Convert `reference/scope_bitstream_2c53t_v120.bin` → `.fs` (`tools/bin2fs.py`):
      722 frames × 160 B + 68 B hdr + 50 B ftr = 115638 B; every per-frame CRC-16 valid.
- [x] `gowin_unpack -d GW1N-2` produces a fabric netlist (exit 0, `tools/m5/scope_unpacked.v`).
- **Validation:** clean unpack + plausibility ✅ — 847 LUT4, 879 DFFs, 192 ALU,
      4 BSRAM (all), DDR I/O (IDDRC/ODDRC), 59 IOB, 37k routes. Real scope design.
- Caveat: PLL present in the stream (config codes 107/108) but only partially decoded
      (no full RPLLA instance) — the M4a PLL follow-up; does not block the unpack.

## M6 — Upstream contribution 🟡 prepared (2026-06-13)
- [x] Consolidated all bring-up changes into `tools/patches/gw1n2-support.patch`
      (7 files) + `tools/patches/nextpnr-gw1n2-gen.patch`; staged-PR plan in
      `docs/04-contributing.md` ("GW1N-2 staging plan"). Ready for David to submit.
- [ ] PR the GW1N-2 chipdb + recognition entry to Apicula (NEEDS DAVID — outward-facing
      community step: ping `yrabbit` on Matrix, open tracking Issue, open staged PRs).
- [x] (stretch) nextpnr-himbaechel device data for GW1N-2 → **authored a custom
      bitstream** (registered AND round-trip). PLL bel still skipped (M4) and not
      hardware-verified, so this is a working prototype, not yet upstream-ready.

## Effort / reality check
- Days-to-weeks of iterative work, mostly mechanical once M0 is solid.
- The long pole is **M3 (routing)** — always the largest surface in FPGA RE.
- Biggest risk: **macOS friction.** Budget for a Linux VM/container early; fighting
  the toolchain on macOS will cost more than standing up Linux once.
- This unlocks **unpacking**. *Authoring* a custom bitstream additionally needs
  nextpnr-himbaechel device data (M6 stretch) — or just use Gowin's free closed IDE,
  which needs none of this.

## Decision checkpoint before starting
Worth a deliberate "do we actually want this?" gate. It's a real side project that
helps the community, but **none of the 2C53T firmware features we care about
(better FFT, CAN/protocol triggers, software triggering) need it** — those are
MCU-side. Pursue this for: reading the stock scope bitstream, settling the
"is the DMM in the fabric?" question, or staying fully open-source on a future
custom bitstream. Not for general firmware progress.
