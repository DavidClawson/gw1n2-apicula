# 01 — Environment setup

> Goal of this stage: get a working Apicula dev environment, and **reproduce a
> known-good device build (GW1NZ-1) from scratch** so we have a verified template
> before touching GW1N-2. If we can't rebuild an existing chipdb, we're not ready
> to make a new one.

> ✅ **Verified 2026-06-13** against a fresh clone of `YosysHQ/apicula` (pin
> `GWVERSION = 1.9.10.03`). The script names and build mechanism below are now
> confirmed against the real repo (earlier drafts had placeholders). Clone lives at
> `tools/apicula/`.

## 0. Platform

Linux. The fuzzer shells out to Gowin's `gw_sh` with an `LD_PRELOAD` of a vendor
`.so` (`apycula/codegen.py:270`), and the whole flow assumes a Linux filesystem
layout for `$GOWINHOME`. **Do not attempt the build/fuzz flow on macOS** — the Mac
is the workstation; the build runs on a Linux box (David's headless Ubuntu server,
or a VM/container). See `setup.sh` for a runnable bootstrap and `docs/05-needs-david.md`
for the human-only blockers.

## 1. Gowin EDA (the compile oracle) — NEEDS DAVID

- Download **Gowin EDA, version `1.9.10.03`** specifically. That is the version
  Apicula pins (`GWVERSION`) and tests against; the chipdb is built by parsing this
  version's vendor data files, and newer versions "may work but have not been tested"
  (Apicula readme). Mismatched versions are a known source of parser breakage — get
  1.9.10.03 if at all possible.
- The **Education edition** is free (no license server) and covers the small parts
  including the GW1N-2 family. Download is registration-walled at gowinsemi.com.
- The fuzzer drives the **headless** CLI, not the GUI:
  - synthesis/PnR shell: `$GOWINHOME/IDE/bin/gw_sh`
  - it is invoked with `LD_PRELOAD=$GOWINHOME/Programmer/bin/libfontconfig.so.1`
    (so the install needs both `IDE/` and `Programmer/` subtrees).
- **`$GOWINHOME`** is the install root. The build reads per-device vendor data from:
  ```
  $GOWINHOME/IDE/share/device/<DEVICE>/<DEVICE>.fse   # fabric structure
  $GOWINHOME/IDE/share/device/<DEVICE>/<DEVICE>.dat   # data
  $GOWINHOME/IDE/share/device/<DEVICE>/<DEVICE>.tm    # timing
  ```
  For our target the folder is `.../device/GW1N-2/GW1N-2.{fse,dat,tm}` (see
  `docs/02` — GW1N-2 shares this `.fse`, md5 `4e23e179…`, with the GW1N-1P5 /
  GW1NR-2 pin-variants; same die).

## 2. Apicula (the RE toolchain)

```bash
git clone https://github.com/YosysHQ/apicula      # already cloned to tools/apicula
cd apicula
python3 -m venv .venv && . .venv/bin/activate
pip install -e .          # editable install so we can add a device
```

`requirements.txt` does not exist in the current repo; `pip install -e .` pulls the
declared deps (numpy etc.). Apicula finds the vendor data via the **`GOWINHOME`
environment variable** (confirmed: `chipdb_builder.py`, `codegen.py`, `tm_parser.py`
all read `os.getenv("GOWINHOME")`; the `Makefile` hard-errors if it is unset). There
is no `--gowinhome` flag — it is the env var.

## 3. yosys + nextpnr-himbaechel (for round-trip validation)

- `yosys` with the Gowin (`synth_gowin`) flow.
- `nextpnr-himbaechel` built with Gowin support.
- These let us synthesize a small test design → place & route → `gowin_pack` →
  `gowin_unpack`, which is how we validate each fuzzing milestone.
- **Easiest source: the YosysHQ OSS-CAD-Suite nightly bundle** (ships yosys +
  nextpnr-himbaechel + apycula together). `setup.sh` fetches it. Building from
  source is the fallback.

## 4. Reproduce a known-good build (the template gate)

Before any GW1N-2 work, rebuild an **existing** device's chipdb end-to-end. The
build is a Makefile target; each `apycula/<DEVICE>.msgpack.xz` is produced by
`python3 -m apycula.chipdb_builder <DEVICE>`:

```bash
export GOWINHOME=/path/to/gowin            # install root (contains IDE/, Programmer/)
cd tools/apicula
make apycula/GW1NZ-1.msgpack.xz            # builds just the GW1NZ-1 chipdb
# equivalently: python3 -m apycula.chipdb_builder GW1NZ-1
```

Success criteria:
- The build produces a `GW1NZ-1.msgpack.xz` matching (or functionally equal to) the
  shipped one.
- A trivial blinky round-trips: `yosys → nextpnr-himbaechel → gowin_pack →
  gowin_unpack` with no errors.

If both pass, the toolchain + oracle + vendor-data plumbing all work, and GW1NZ-1
becomes our fork template for GW1N-2. If either fails, stop and fix the environment
— do not proceed to new-device work on a shaky base.

> Note: `GW1N-2` is **not** yet in the `Makefile` `all:` target nor in the `DEVICES`
> table in `apycula/chipdb_builder.py` — adding those entries is M1 work, not setup.

## 5. Sanity-check our target loads as far as the IDCODE gate

Apicula's `gowin_unpack` reads the **ASCII `.fs`** text format, so the raw `.bin`
must first be converted (see `reference/NOTES.md` and the planned binary→`.fs`
converter). The device-ID gate lives in `apycula/bslib.py::read_bitstream`
(the `if ba[0] == 0x06:` block, ~L96–127): a literal byte-match on the device-ID
command, each branch setting `padding`/`compress_padding`. Our
`06 00 00 00 01 20 68 1b` hits the `else: raise ValueError("Unsupported device")`
on stock Apicula — that failure IS the baseline.

`tools/patches/0001-bslib-recognize-gw1n2.patch` adds the matching `elif` branch
(staged, already applied to the clone) so recognition no longer blocks us. Its
`padding`/`compress_padding` values are provisional (copied from GW1NZ-1) and must
be confirmed once we can build/diff real GW1N-2 streams.
