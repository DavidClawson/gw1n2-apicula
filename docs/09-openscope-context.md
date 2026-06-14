# Origin & relationship to the OpenScope project

This page holds the project-specific backstory that used to live in the README, so
the README can stay device-first for the general Apicula/Gowin audience. None of
this is required to understand or contribute to the GW1N-2 chipdb work.

## Why this project exists

This effort started as a side quest of **OpenScope** — an open-firmware project for
the **FNIRSI 2C53T** handheld oscilloscope. That scope's FPGA is a Gowin
**GW1N-UV2** (GW1N-2 family), and [Project Apicula](https://github.com/YosysHQ/apicula)
doesn't yet support that device. Without support we can neither *unpack* the stock
FPGA bitstream into a fabric netlist nor *author* our own bitstream through the
fully-open flow. Building the chipdb fixes both — and benefits the whole open-FPGA
community, not just this scope.

It's kept as a **standalone repo, deliberately outside** the OpenScope firmware
repo. The dependency arrow is one-way: OpenScope does not depend on this work.

## The validation target is a scope bitstream

The day a GW1N-2 chipdb exists, the first real-world test is to `gowin_unpack` the
2C53T's stock FPGA bitstream cleanly. That file is our north star (and a handy
source of IDCODE/header sanity-checks), but it is **never an input** to building the
chipdb — see [the README's note on not needing a real bitstream](../README.md) and
[`reference/NOTES.md`](../reference/NOTES.md). It is a byte-exact slice of FNIRSI's
proprietary firmware, so it is **gitignored, not redistributed**; reproduce it
locally from the recipe + sha256 in `reference/NOTES.md`.

## What this does and does not unlock for OpenScope

Most "advanced" scope features — FFT, protocol-aware triggers (CAN), and the like —
are **MCU-side firmware** and need no FPGA changes at all. They do not depend on
this project. This work only matters for:

- **(a) reading** the stock scope bitstream (understanding what the FPGA fabric
  actually does), or
- **(b) authoring** a custom GW1N-2 bitstream through the fully-open toolchain.

For authoring alone, Gowin's free (closed) EDA IDE already works today with zero
fuzzing. The Apicula route is the "stay 100% open-source / read the stock image"
path.

## Sister-repo vision

Once two milestones land — (1) the chipdb merges upstream into Apicula, and (2) a
working unpack→modify→repack round-trip exists — this repo is intended to become the
**experimental FPGA sister project** to
[OpenScope](https://github.com/DavidClawson/OpenScope-2C53T):

- **Here:** the toolchain, the fabric knowledge, and experiments — e.g. an
  `examples/` folder (hello-world, minimal known-good designs) and an
  `experiments/` folder (modified FPGA behaviors, alternate trigger logic, custom
  bitstreams). High-churn, no stability promise.
- **In OpenScope:** shipped, tested, supported scope behavior.

That seam keeps the wild experimentation out of the main scope repo while giving it
a real home.
