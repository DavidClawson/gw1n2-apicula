# GW1N-2 Apicula Support — Bitstream RE Side Project

**Goal:** add open-source bitstream support for the **Gowin GW1N-2** (IDCODE `0x0120681B`)
to [Project Apicula](https://github.com/YosysHQ/apicula), the community Gowin FPGA RE
toolchain that backs `yosys` + `nextpnr-himbaechel`.

This is a **standalone curiosity project**, deliberately kept *outside* the
`osc` (FNIRSI 2C53T firmware) repo. It exists because that scope uses a Gowin
**GW1N-UV2** (GW1N-2 family), and Apicula does not yet support that device — so we
can neither *unpack* the stock FPGA bitstream into a fabric netlist nor *author*
our own bitstream through the open flow. Building the chipdb fixes both, and
benefits the whole open-FPGA community, not just us.

## The one counterintuitive fact

**We do not need our scope's bitstream to do this work.** Building device support
means *generating thousands of fresh, tiny bitstreams from Gowin's own tool and
diffing them* — our scope bitstream is never an input. It is only the
**validation target**: the very first thing we'll try to `gowin_unpack` once a
GW1N-2 chipdb exists. It is *not redistributed in this repo* (it's a byte-exact
slice of FNIRSI's proprietary stock firmware); reproduce it locally from the
recipe + sha256 in `reference/NOTES.md`. It serves only as that north star and
for IDCODE/header sanity-checks.

## Why GW1N-2 specifically is the wall

Apicula 0.32 (latest on PyPI) ships chipdbs for exactly these 10 devices:

```
GW1N-1, GW1N-4, GW1N-9, GW1N-9C, GW1NS-4, GW1NZ-1,
GW2A-18, GW2A-18C, GW5A-25A, GW5AST-138C
```

No GW1N-2. The IDCODE gate is a literal byte-match list in `apycula/bslib.py`
(`read_bitstream`, ~lines 96–127); our stream's device-ID command
`06 00 00 00 01 20 68 1b` (= IDCODE `0x0120681B`) matches nothing and raises
`ValueError("Unsupported device")`. That check runs on the IDCODE *embedded in the
bitstream*, **before** any `-d DEVICE` flag's database loads — so no flag works
around it. The fix is a real GW1N-2 chipdb, not a config tweak.

**Closest existing relative:** `GW1NZ-1`, IDCODE `0x0100681B` — shares the `…681B`
family tail, differs from ours in one byte. It's the natural template to fork from.

## The method, in one paragraph

It's **differential fuzzing**, not random guessing. You use Gowin's own (free,
closed) EDA tool as a compile *oracle*: emit a minimal design that sets exactly one
fabric feature (one LUT truth table, one routed wire, one IO buffer), compile it,
emit a near-identical design differing only in that feature, compile that too, and
**diff the two bitstreams** — the bits that flipped are the bits that control that
feature. Repeat systematically over the whole tile grid to build the
bit ↔ feature map (the "chipdb"). Apicula *also* parses Gowin's shipped internal
fabric/timing files (`.fse` / `.dat` / `.tm`), which already encode much of the
structure — so it's part vendor-file RE, part diff-fuzzing to confirm bit
positions. Bottom-up order: grid/IO → LUT/DFF → routing → BRAM → PLL.

## Status

- [x] Confirmed the blocker (GW1N-2 absent from Apicula device DB)
- [x] Extracted + verified the target bitstream (`reference/`, sha256 `5a0e7338…`)
- [ ] Environment set up (Gowin EDA + Apicula clone + reference build) — `docs/01`
- [ ] GW1NZ-1 reference build reproduced as a template — `docs/01`
- [ ] GW1N-2 grid/IO mapped — `docs/02`
- [ ] GW1N-2 logic primitives mapped (LUT/DFF) — `docs/02`
- [ ] GW1N-2 routing mapped — `docs/02`
- [ ] GW1N-2 BRAM/PLL mapped — `docs/02`
- [ ] `gowin_unpack` succeeds on `reference/scope_bitstream_2c53t_v120.bin`
- [ ] (stretch) nextpnr-himbaechel device data → author a custom GW1N-2 bitstream

## What you can do with this today

Be clear-eyed about the gate: **this is work-in-progress research, not yet a
usable tool.** The headline workflow — `gowin_unpack -d GW1N-2 …` — does not run
for anyone until the GW1N-2 chipdb exists and lands in Apicula (the unchecked
boxes above). Until then, here's the honest breakdown by audience:

| You want to… | Status today |
|---|---|
| **Read the RE story** (how Gowin bitstreams work, how to fuzz a chipdb) | ✅ Ready now — start at `docs/00` |
| **Reproduce the recon** (header/IDCODE parse, `bin2fs`, format checks) | ✅ Runnable now (Python; no Gowin EDA needed) |
| **Run the fuzzing flow** (build the chipdb yourself) | ⚠️ Needs Gowin EDA + a Linux box — see `docs/01`, `docs/05` |
| **Unpack *your own* 2C53T bitstream** | ⛔ Blocked on the chipdb (the milestone work above) |
| **Modify FPGA behavior and reflash** (experimental features) | ⛔ Needs unpack **and** a working repack round-trip (`tools/roundtrip/`, early) |

**Two unlock moments to watch for:** (1) the chipdb merging upstream into Apicula
flips this from "read along" to "anyone can unpack their bitstream"; (2) a working
unpack→modify→repack round-trip flips it to "experimenters can bring their own
designs." This repo is intended to become the experimental sister project to the
[OpenScope](https://github.com/DavidClawson/OpenScope-2C53T) firmware work once those land — the toolchain and
fabric-knowledge home, while shipped/supported scope behavior stays in OpenScope.

## Docs

- `docs/00-background.md` — the device, the IDCODE wall, and how bitstream fuzzing works
- `docs/01-environment-setup.md` — Gowin EDA, Apicula clone, reproduce a known-good device build
- `docs/02-methodology.md` — the bottom-up fuzzing plan, using GW1NZ-1 as the template
- `docs/03-workplan.md` — milestone checklist and how we'll know each step worked
- `docs/04-contributing.md` — how to land GW1N-2 support upstream the way maintainers expect
- `docs/05-needs-david.md` — the human-only blockers (Gowin EDA install, Linux env)
- `setup.sh` — runnable env bootstrap for the Linux box (verified against the real repo)

## Relationship to the firmware project

Separate on purpose. The `osc` firmware work does **not** depend on this — FFT,
protocol-aware triggers (CAN), and most "advanced" scope features are
**MCU-side firmware** and need no FPGA changes at all. This project only matters
for (a) *reading* the stock scope bitstream, or (b) *authoring* a custom one through
the fully-open toolchain. For authoring alone, Gowin's free closed IDE already works
today with zero fuzzing — the Apicula route is the "stay 100% open-source / read the
stock image" path.

## License / intent

Any chipdb produced here is intended to be **contributed upstream to Apicula**
(MIT). This folder is workspace + notes, not a fork; the real work lands in a clone
of the Apicula repo (see `docs/01`).
