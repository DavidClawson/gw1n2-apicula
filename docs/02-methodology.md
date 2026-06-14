# 02 — Methodology: mapping the GW1N-2 fabric

> Premise: GW1NZ-1 is already supported and is our closest relative (`…681B` tail).
> Most of the *conceptual* work — what each primitive looks like in bits, how to
> drive the Gowin oracle, how to diff — is inherited from it. The GW1N-2-specific
> effort is almost entirely **geometry**: a different grid size and different
> absolute bit positions. Work bottom-up; validate each layer before the next.

## Head start: GW1N-2 is already partially scaffolded in Apicula

Confirmed against the clone (2026-06-13) — GW1N-2 is *referenced* but not yet a
buildable device, so we inherit some groundwork:

- `apycula/chipdb.py:675` — a `elif device == 'GW1N-2':` routing branch already exists.
- `apycula/gowin_pack.py:2999` — GW1N-2 is already named in a device special-case group.
- `apycula/ini_h4x.py:69` — the GW1N-2 family group is enumerated
  (`'GW1N-2', 'GW1NR-2', 'GW1N-1P5', 'GW1N-2B', …`).
- `apycula/chipdb.py:2325` — a comment about IOT2/IOT3A pins for GW1N-2.

But the two entries that make a device *build* are **missing**: GW1N-2 is not in the
`DEVICES` table (`chipdb_builder.py`) nor the `Makefile` `all:` target. Adding those
two, then iterating per-subsystem, is the M1 starting move.

**Vendor data folder:** `$GOWINHOME/IDE/share/device/GW1N-2/GW1N-2.{fse,dat,tm}`.
Per `tools/apicula/doc/device_grouping.md`, GW1N-2 shares its `.fse`
(md5 `4e23e1797693721610674e964cd550f1`) with GW1N-1P5, GW1N-2B, GW1NR-2, GW1NZR-2,
etc. — those are the **same die**, different pinout/package. (Note: `GW1NS-2` is a
*different* die — don't conflate.) So the `device` field in our `DEVICES` entry is
`"GW1N-2"`; the `partnumber` for the FNIRSI part (GW1N-UV2) still needs pinning from
the datasheet/Gowin part list.

## How much is "parse" vs "fuzz"

Try the cheap path first at every layer: Apicula's `fse_parser` may already extract
the structure straight from Gowin's `.fse/.dat/.tm` files for GW1N-2 (the vendor
ships per-device data). If the parser yields a plausible grid/primitive map for
GW1N-2 out of the box, much of "fuzzing" reduces to **confirming** bit positions
with a handful of targeted diff experiments rather than exhaustively sweeping. Only
fuzz from scratch where the vendor data is missing or ambiguous.

## Layer 1 — Grid + IO

- Extract grid dimensions (rows × cols of tiles) for GW1N-2 from the vendor data.
- Map IO: which package pins → which IO tiles, bank assignments, IO standards.
- **Diff experiment:** a one-pin design (just an input or output buffer on a single
  pin) vs. the empty design → isolates that IO tile's enable/config bits.
- **Validate:** generate a design lighting a few specific pins; confirm the bits land
  in the expected tiles.

## Layer 2 — Logic primitives (LUT / DFF)

- **LUT truth-table bits:** compile a LUT4 with truth table `0x0000`, then `0x0001`,
  `0x0002`, … and diff. Each diff reveals one truth-table bit's position. 16 bits per
  LUT4; positions should be regular across the grid (inherit the pattern from GW1NZ-1
  and confirm).
- **DFF config:** clock enable, set/reset polarity, sync/async — one-feature-at-a-time
  designs, diffed.
- **Validate:** pack a known LUT+DFF design, unpack it, check the recovered truth
  tables/config match what we put in.

## Layer 3 — Routing

- The biggest layer: the config bits that set each routing mux (which source wire
  drives each destination).
- **Diff experiment:** route signal A→B one way, then force a different route, diff.
  Apicula's existing routing-fuzz scripts parameterize this; the GW1N-2 work is
  running them against the GW1N-2 grid and recording positions.
- **Validate:** a multi-tile design where signals must traverse known wire paths;
  confirm unpack recovers the routes.

## Layer 4 — Hard blocks (BRAM, PLL)

- **BRAM:** map the per-block config bits *and* the init-content bit layout (so
  `gowin_unpack` can dump RAM contents — relevant later if we ever look for meter/UI
  data in a fabric image). 4 blocks, 72 Kbit total.
- **PLL:** 1 PLL — map its divider/multiplier/phase config bits.
- **No DSP:** GW1N-2 has no hardware multipliers, so the DSP-fuzzing class is skipped
  entirely.

## Layer 5 — Validation against the real target

1. Round-trip increasingly complex synthetic designs (pack → unpack, compare).
2. Then the real prize: convert `reference/scope_bitstream_2c53t_v120.bin` to `.fs`
   and `gowin_unpack` it. A clean unpack into a sensible fabric netlist (and CRC-16
   passing per frame) is the project's success signal.
3. Spot-check the unpacked netlist for plausibility (IO count consistent with the
   board, BRAM present, etc.).

## A note on what the unpack will and won't tell us

`gowin_unpack` yields a **flat, nameless fabric netlist** — LUTs/DFFs/BRAM/IO +
routing, no signal names or module hierarchy. Useful for *what the logic does*
(e.g. tracing whether binary→BCD conversion exists in the fabric — the discriminator
for "is the DMM in the FPGA or behind it"), painful to read. It is **not** a Verilog
decompiler. Set expectations accordingly.
