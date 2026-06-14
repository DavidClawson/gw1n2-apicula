# 04 — Contributing to Apicula (doing it right from the start)

> Researched 2026-06-13 from the `YosysHQ/apicula` repo, its git/PR history, and the
> readme. The goal: land GW1N-2 support upstream the way the maintainers expect, not
> as a surprise mega-patch.

## TL;DR — the contribution model

- **License: MIT** (`LICENSE`, © 2019 Pepijn de Vos). Our additions are MIT.
- **Mechanism: plain GitHub Pull Requests** against `YosysHQ/apicula`, base branch
  `master`. No fork-by-email, no patch list.
- **No CLA, no DCO/sign-off, no CONTRIBUTING.md, no PR template, no code of conduct.**
  The process is informal: coordinate in chat → open PR(s) → maintainer reviews & merges.
- **Device bring-up is staged into many small, feature-scoped PRs** — not one big one.
  This is the single most important norm to follow.

## Where to talk first

The readme points contributors to a single bridged room:

- **Matrix:** `#apicula:matrix.org` — https://matrix.to/#/#apicula:matrix.org
- **IRC (Libera.Chat):** `#yosys-apicula` — https://web.libera.chat/#yosys-apicula
  (Matrix ↔ IRC are bridged; same room.)
- **GitHub Issues** are enabled and used. **Discussions are disabled.**

**Recommended:** announce intent in the Matrix/IRC room (ping `yrabbit`) and/or open
a tracking Issue ("Add GW1N-2 support") before sending a large bring-up PR. This is
where you confirm nobody else is mid-flight on GW1N-2 and agree on staging.

## Who reviews / merges

- **@yrabbit** — *the* active maintainer and primary device-bring-up author; merges
  essentially all PRs today. **Primary contact for GW1N-2.**
- **@pepijndevos** — project founder/copyright holder; still lands substantive PRs.
- **@gatecat** — nextpnr-himbaechel maintainer; handles the himbaechel/IO side and
  device-variant fixups.

## How a new device actually lands (precedent)

Bring-up is a **series of small per-subsystem PRs**, titled `<DEVICE>. <feature>.`
The modern template is the **GW5A** family (2025→2026). Examples:

| PR | Scope | Rough size |
|----|-------|-----------|
| [#360](https://github.com/YosysHQ/apicula/pull/360) "GW5A. Implement simple IO and logic." | initial bring-up | ~+1000/−100, ~20 files |
| [#181](https://github.com/YosysHQ/apicula/pull/181) "Add support for the GW2A series" | initial bring-up | small (~+65) |
| [#446](https://github.com/YosysHQ/apicula/pull/446) "Add GW5A clock routing and BSRAM init" | mid bring-up | ~+1400 |
| [#463](https://github.com/YosysHQ/apicula/pull/463) / [#464](https://github.com/YosysHQ/apicula/pull/464) | sub-variant IO/BSRAM | small |

**Staging order** that maintainers expect (matches our `docs/02`/`docs/03`):
IO + logic → ALU/LUTRAM → clocks/PLL → BSRAM → (DSP — N/A for GW1N-2) → HCLK/etc.
Initial PR ≈ IO + simple logic; everything else follows feature-by-feature.

## Files a device PR typically touches

From #360's diff (the canonical set — map onto our plan):

- `Makefile` — add `apycula/GW1N-2.msgpack.xz` to the `all:` target.
- `apycula/chipdb_builder.py` — add a `GW1N-2` entry to the `DEVICES` table
  (`package` / `device` / `partnumber`). **Not present today.**
- `apycula/chipdb.py` — per-device tile/routing/feature branches
  (a `GW1N-2` branch already exists at ~L675 — partial groundwork).
- `apycula/gowin_pack.py` / `gowin_unpack.py` — packer/unpacker special-casing
  (GW1N-2 is already named in a device group at `gowin_pack.py:2999`).
- `apycula/bslib.py` — device-ID recognition (our staged patch 0001).
- `apycula/tiled_fuzzer.py`, plus helpers (`dat19.py`, `wirenames.py`,
  `attrids.py`, `fuse_h4x.py`, …) as needed.
- `examples/<device>/` — a Makefile + `.v` + `.cst` blinky so the **toolchain CI**
  exercises the new device.

## CI you must satisfy

Three GitHub Actions run on every PR (`.github/workflows/`):

1. **`chipdb.yml`** — builds **all** chipdbs (`make`) inside a Docker image pinned to
   Gowin tools `1.9.10.03`, then builds/installs the wheel. → a new device must build
   via `make` against that exact vendor version, so add it to the Makefile `all:`.
2. **`toolchain.yml`** — builds yosys + nextpnr and runs `examples/` on both a `dev`
   and a `stable` toolchain → ship a working `examples/gw1n2/` so this passes.
3. `docker-build.yml`, `yowasp_examples.yml`.

## Our concrete path to a first PR

1. Coordinate on Matrix `#apicula:matrix.org` (ping `yrabbit`); open a tracking Issue.
2. Reproduce the GW1NZ-1 build locally (M0 gate) against Gowin `1.9.10.03`.
3. Add `GW1N-2` to the `DEVICES` table + Makefile; get `fse_parser`/`chipdb_builder`
   to emit a GW1N-2 grid (M1).
4. First PR ≈ "GW1N-2. Initial IO + logic." mirroring #360, **with an
   `examples/gw1n2/` blinky** so CI is green.
5. Follow with small per-subsystem PRs (routing, BSRAM, PLL) — each validated by a
   round-trip, each its own PR.
6. Expect `yrabbit` to review/merge. No sign-off/CLA. Keep additions MIT.

## Useful upstream docs to read (in `tools/apicula/doc/`)

`device_grouping.md` (why GW1N-2 shares vendor files with its pin-variants),
`filestructure.md` (vendor file layout), `architecture.md`, `commandstructure.md`,
and the per-subsystem notes (`alu.md`, `bsram-fix.md`, `hclk.md`, `longwires.md`,
`muxes.md`, `special-pins.md`). The GitHub **wiki** is per-primitive cell reference,
not a process guide. There is **no** "how to add a device" doc — this file is ours.

---

## GW1N-2 staging plan — ready to submit (M6, prepared 2026-06-13)

All bring-up changes are captured as a single reviewable diff in
`tools/patches/gw1n2-support.patch` (7 files, ~65 insertions) plus the nextpnr-side
generator patch `tools/patches/nextpnr-gw1n2-gen.patch`. The work is **done and
validated** (M0–M5: the real scope bitstream unpacks); what remains is the human,
outward-facing step of coordinating with the maintainers and opening PRs.

**Submission is David's call** (community interaction). When ready, ping `yrabbit`
on Matrix `#apicula:matrix.org`, open a tracking Issue ("Add GW1N-2 support"), then
stage these PRs (smallest/most-independent first, per the project norm):

| # | PR title | Files / hunks | Notes |
|---|----------|---------------|-------|
| 1 | `dat_parser: support partType-1 .dat files` | `dat_parser.py` | **Most valuable standalone** — unblocks the whole GW1N-2/1P5/2B/R-2/ZR-2 family, not just GW1N-2. Self-contained. RE'd as "partType-0 layout + appended extended table at 0x7b4a8". |
| 2 | `GW1N-2. Recognize device + build chipdb` | `bslib.py` (IDCODE 0x0120681B), `chipdb_builder.py` (DEVICE_PARAMS→GW1N-1P5C, _chip_id, GSR), `gowin_unpack.py` (_packages), `Makefile` | Core recognition + `make apycula/GW1N-2.msgpack.xz`. |
| 3 | `GW1N-2. Pinout, IO config, OSC` | `chipdb.py` (json_pinout, get_pins allowlist, OSCO stub, non-fatal unknown IO cfg) | IO/special-function. The 10 `UNKNOWN_CFG_*` special-pin codes are flagged as a known TODO (don't block). |
| 4 | `GW1N-2. rPLL (partial)` — **HOLD** | `chipdb.py` (fse_pll ttyp 50, dat_portmap -1 guard) | RPLLA bel + config build, but the portmap lives in the partType-1 extended table and is not yet fully decoded (M4a follow-up). **Hold until the portmap + attr codes 107/108 are finished** — a PLL PR with a known routing gap likely won't be accepted. |
| — | `examples/gw1n2/` blinky | new dir | CI (`toolchain.yml`) runs `examples/` — ship a working blinky so the PR stays green. Our `tools/roundtrip/` design is the seed. |

**Separate repo (YosysHQ/nextpnr, reviewer `gatecat`):**
`tools/patches/staged/nextpnr/01-gw1n2-arch-gen.patch` — the **entire** nextpnr-side
change, just 2 files: add `GW1N-2` to `ALL_HIMBAECHEL_GOWIN_DEVICES` in
`himbaechel/uarch/gowin/CMakeLists.txt`, and in `gowin_arch_gen.py` add GW1N-2 to the
`simple_io` set + emit the PLL tile without a PLL bel when the chipdb has no `RPLLA`
(PLL-skip; drop once apicula's PLL lands). Plus the example `examples/gw1n2/`
(`tools/patches/staged/examples-gw1n2/`).

**Correction (2026-06-13): no `gowin.cc` change is needed.** Earlier notes assumed a
device→family regex fix because the GW1N-1P5C partnumber (`GW1N-UV1P5…`) parses to
family `GW1N-1`. It isn't required — the examples Makefile passes `--vopt family=`
explicitly as the house idiom (`tangnano9k` → `--vopt family=GW1N-9C`,
`tangnano20k` → `--vopt family=GW2A-18C`), and our `examples/gw1n2/` does the same
(`--vopt family=GW1N-2`). Validated against a from-source nextpnr build with
`-DHIMBAECHEL_GOWIN_DEVICES="GW1N-2"` (the CMake `foreach` builds each device
independently): the build path runs `gowin_arch_gen.py -d GW1N-2` and produces
`chipdb-GW1N-2.bba`/`.bin` with no errors. See `tools/patches/staged/nextpnr/`.

**Local-only (do not upstream as GW1N-2 work):** `codegen.py`'s `$GOWIN_LD_PRELOAD`
override is a headless-`gw_sh` build aid for our Ubuntu 24.04 box, unrelated to
GW1N-2. If useful upstream, send it as its own tiny independent PR.

**Caveats to disclose in the PRs:** PLL portmap/attr-codes incomplete (M4a); not yet
hardware-verified on the scope; 10 `UNKNOWN_CFG_*` IO codes + OSCO ports stubbed.
