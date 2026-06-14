# GW1N-2 Apicula Support

**Open-source bitstream reverse-engineering to add the Gowin GW1N-2 (IDCODE
`0x0120681B`) to [Project Apicula](https://github.com/YosysHQ/apicula)** — the
community Gowin FPGA RE toolchain behind `yosys` + `nextpnr-himbaechel`.

Apicula 0.32 ships chipdbs for 10 Gowin devices; the GW1N-2 isn't one of them. This
repo builds the missing chipdb — through differential fuzzing of Gowin's own EDA
tool plus parsing its shipped fabric/timing data — so the open flow can *unpack*
(and eventually *author*) GW1N-2 bitstreams.

> ⚠️ **Status: work-in-progress research, not yet a usable tool.** The headline
> `gowin_unpack -d GW1N-2 …` workflow does not run for anyone until the chipdb is
> built and merged upstream. See [What you can do today](#what-you-can-do-today).

> This work began as a side quest of an open-firmware project for the FNIRSI 2C53T
> oscilloscope (whose FPGA is a GW1N-2). That backstory — and how it relates to that
> scope — lives in [`docs/09-openscope-context.md`](docs/09-openscope-context.md);
> it isn't needed to understand or contribute to the chipdb work.

## Why GW1N-2 specifically is the wall

Apicula 0.32 (latest on PyPI) ships chipdbs for exactly these 10 devices:

```
GW1N-1, GW1N-4, GW1N-9, GW1N-9C, GW1NS-4, GW1NZ-1,
GW2A-18, GW2A-18C, GW5A-25A, GW5AST-138C
```

No GW1N-2. The IDCODE gate is a literal byte-match list in `apycula/bslib.py`
(`read_bitstream`, ~lines 96–127); a GW1N-2 stream's device-ID command
`06 00 00 00 01 20 68 1b` (= IDCODE `0x0120681B`) matches nothing and raises
`ValueError("Unsupported device")`. That check runs on the IDCODE *embedded in the
bitstream*, **before** any `-d DEVICE` flag's database loads — so no flag works
around it. The fix is a real GW1N-2 chipdb, not a config tweak.

**Closest existing relative:** `GW1NZ-1`, IDCODE `0x0100681B` — shares the `…681B`
family tail, differs in one byte. It's the natural template to fork from.

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

You do **not** need a real-world GW1N-2 bitstream to do any of this — device support
is built entirely from fresh, tiny bitstreams generated and diffed on the fly. A
real-world stream is only useful as a final *validation target*: the first thing
to `gowin_unpack` once the chipdb exists. (The one used here is gitignored, not
redistributed — see [`reference/NOTES.md`](reference/NOTES.md).)

## Status

- [x] Confirmed the blocker (GW1N-2 absent from Apicula device DB)
- [x] Extracted + verified a real-world validation bitstream (`reference/`, sha256 `5a0e7338…`)
- [ ] Environment set up (Gowin EDA + Apicula clone + reference build) — `docs/01`
- [ ] GW1NZ-1 reference build reproduced as a template — `docs/01`
- [ ] GW1N-2 grid/IO mapped — `docs/02`
- [ ] GW1N-2 logic primitives mapped (LUT/DFF) — `docs/02`
- [ ] GW1N-2 routing mapped — `docs/02`
- [ ] GW1N-2 BRAM/PLL mapped — `docs/02`
- [ ] `gowin_unpack` succeeds on the validation bitstream
- [ ] (stretch) nextpnr-himbaechel device data → author a custom GW1N-2 bitstream

## What you can do today

Be clear-eyed about the gate: **this is work-in-progress research, not yet a usable
tool.** The headline `gowin_unpack -d GW1N-2 …` workflow does not run for anyone
until the GW1N-2 chipdb exists and lands in Apicula (the unchecked boxes above).
Until then, here's the honest breakdown by audience:

| You want to… | Status today |
|---|---|
| **Read the RE story** (how Gowin bitstreams work, how to fuzz a chipdb) | ✅ Ready now — start at `docs/00` |
| **Reproduce the recon** (header/IDCODE parse, `bin2fs`, format checks) | ✅ Runnable now (Python; no Gowin EDA needed) |
| **Run the fuzzing flow** (build the chipdb yourself) | ⚠️ Needs Gowin EDA + a Linux box — see `docs/01`, `docs/05` |
| **Unpack a real GW1N-2 bitstream** | ⛔ Blocked on the chipdb (the milestone work above) |
| **Modify FPGA behavior and re-pack** (experimental designs) | ⛔ Needs unpack **and** a working repack round-trip (`tools/roundtrip/`, early) |

**Two unlock moments to watch for:** (1) the chipdb merging upstream into Apicula
flips this from "read along" to "anyone can unpack a GW1N-2 bitstream"; (2) a
working unpack→modify→repack round-trip flips it to "experimenters can modify a
GW1N-2 bitstream" — at which point this becomes an experimental sister repo for
custom GW1N-2 work (see [`docs/09`](docs/09-openscope-context.md)).

## Reference value for other GW1N devices

The *bitstreams* this enables are device-locked — a Gowin bitstream carries its own
IDCODE and a die-specific grid/frame layout, so a GW1N-2 image will not load on a
GW1N-1, -4, or -9 (the IDCODE gate rejects it, and the fabric coordinates wouldn't
line up even if forced). There's no "author once, run across the family."

What *does* transfer is the knowledge and the tooling. The GW1N family (the
"LittleBee" generation) shares an architecture — the same LUT4/DFF primitives, IO
block structure, and routing-mux style — and Apicula is built around that, factoring
shared per-die data rather than treating each device as a silo. (GW1N-2 here unpacks
via GW1N-1P5C die data: Gowin's own files already treat these as related dies.) So
the per-tile bit ↔ feature map and the fuzzing scripts (`tools/m*_*.py`) are a
worked **reference implementation of the method**, reusable by anyone bringing
another not-yet-supported Gowin device into Apicula — not just the GW1N-2.

## Honest scope

To be clear about what this is and isn't: the practical goal here is **not** a
clean-sheet rework of the scope's FPGA design. The aim is the narrower, more
tractable one — finding ways to *add features by modifying the existing stock
bitstream*, ideally without fully reverse-engineering the original design. That work
is inherently bound to a specific device and the scope's context.

So for anyone arriving without the 2C53T hardware and that context, this repo is
best read as a **research and reference resource** — a documented method, a chipdb,
and a set of fuzzing tools — rather than a tool you can point at your own board and
immediately use. That's by design, and the cross-family notes above are exactly the
part that travels.

## Docs

- `docs/00-background.md` — the device, the IDCODE wall, and how bitstream fuzzing works
- `docs/01-environment-setup.md` — Gowin EDA, Apicula clone, reproduce a known-good device build
- `docs/02-methodology.md` — the bottom-up fuzzing plan, using GW1NZ-1 as the template
- `docs/03-workplan.md` — milestone checklist and how we'll know each step worked
- `docs/04-contributing.md` — how to land GW1N-2 support upstream the way maintainers expect
- `docs/05-needs-david.md` — the human-only blockers (Gowin EDA install, Linux env)
- `docs/09-openscope-context.md` — origin story + relationship to the OpenScope firmware project
- `setup.sh` — runnable env bootstrap for the Linux box (verified against the real repo)

## License

MIT (see [`LICENSE`](LICENSE)), matching Apicula's license so any chipdb produced
here can be **contributed upstream to Apicula** cleanly. This repo is workspace +
tooling + notes, not a fork; the chipdb work lands in a clone of the Apicula repo
(see `docs/01`).
