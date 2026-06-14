# GW1N-2 Apicula Support — agent orientation

## Read first
Before doing anything, read `README.md`, then `docs/00-background.md` →
`docs/03-workplan.md`. They contain the full plan, the methodology, and the
milestone gates. This file is just the fast orientation.

## What this project is
Add open-source bitstream support for the **Gowin GW1N-2** (IDCODE `0x0120681B`)
to **Project Apicula** (the Gowin RE toolchain behind yosys + nextpnr-himbaechel),
so we can unpack the FNIRSI 2C53T's stock FPGA bitstream into a fabric netlist
(and, stretch, author our own). Standalone side project; the `osc` firmware repo
does **not** depend on it.

## Cheat-sheet facts
- Target device: Gowin GW1N-UV2 (GW1N-2 family). 2,304 LUT4, 2,304 FF, 72 Kbit
  BRAM, 1 PLL, **no DSP**. IDCODE `0x0120681B`.
- Apicula 0.32 ships 10 device DBs; **GW1N-2 is not one** — IDCODE rejected in
  `apycula/bslib.py::read_bitstream` (~L96–127) before any `-d` flag is read.
- Closest supported relative + fork template: **GW1NZ-1**, IDCODE `0x0100681B`.
- Validation target: `reference/scope_bitstream_2c53t_v120.bin`
  (115,638 B, sha256 `5a0e73384e496bdb…`). It is NOT a build input — see
  `reference/NOTES.md`.
- Method: **differential fuzzing** using Gowin EDA as a compile oracle, plus parsing
  Gowin's `.fse/.dat/.tm` vendor data via Apicula's `fse_parser`.

## HARD CONSTRAINTS — what you (the agent) cannot do alone
These require the human (David) and will block the build pipeline until done:
1. **Install Gowin EDA Education** (registration-walled download + GUI installer).
   It is the compile oracle — no chipdb work past recon happens without it.
2. **Stand up a Linux environment** (VM/container). The fuzzing flow assumes Linux;
   this is a macOS host. Do not try to force the full flow on macOS.
3. Anything touching the physical scope hardware.

When you hit one of these, STOP that thread and add it to a clearly-labeled
"Needs David" list rather than faking around it.

## What you CAN do productively right now (no Gowin EDA needed)
This is the right scope for an early session — software prep + recon:
- Clone Apicula (`git clone https://github.com/YosysHQ/apicula`) into a `tools/`
  subdir and map its **actual** build entry points (script names in `docs/01`/`02`
  are ~0.32 guesses — confirm against the real repo and correct the docs).
- Write + unit-test a **binary→`.fs` converter** for our bitstream (Apicula's
  `gowin_unpack` reads ASCII `.fs`, not raw binary). Verify it reproduces the
  documented header (sync `a5c3`, IDCODE at 0x1E, frame-count cmd at 0x40).
- Draft the trivial `bslib.py` patch adding IDCODE `0x0120681B` (don't expect it to
  *work* yet — there's no chipdb — but stage it).
- Investigate whether Apicula's `fse_parser` can emit a GW1N-2 grid from vendor data
  (document what vendor files would be needed, and from which Gowin install path).
- Turn `docs/01-environment-setup.md` into a runnable `setup.sh` for the eventual
  Linux box, and produce a precise "Needs David" checklist.

## Working rules
- Keep generated tooling under `tools/`; keep notes in `docs/`. Don't pollute
  `reference/`.
- When you confirm or correct a fact about Apicula's internals, **update the docs**
  (especially the script-name placeholders in `docs/01`/`02`).
- This folder is not yet a git repo; don't `git init` or commit unless asked.
- Success for an early session = software prep done + a crisp human-only blocker
  list, NOT a finished chipdb (that's days-to-weeks and gated on the constraints above).
