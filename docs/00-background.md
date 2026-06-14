# 00 — Background: the device, the wall, and how bitstream fuzzing works

## The device

- **Chip:** Gowin GW1N-UV2 (GW1N-2 family), on the FNIRSI 2C53T scope board.
- **Resources** ([Gowin DS100 datasheet](https://cdn.gowinsemi.com.cn/DS100E.pdf)):
  2,304 LUT4 · 2,304 FF · 72 Kbit block SRAM (4 blocks) · 18 Kbit shadow SRAM ·
  96 Kbit user flash · 1 PLL · **no hardware DSP/multiplier blocks**.
- **IDCODE:** `0x0120681B`.
- Non-volatile (retains its config across power cycles), but the 2C53T stock
  firmware nonetheless re-uploads a fresh bitstream over SPI3 at every boot.

## The wall

Project Apicula is the open-source RE of the Gowin bitstream format — the Gowin
analogue of Project IceStorm (Lattice iCE40), Project Trellis (ECP5), and Project
X-Ray (Xilinx 7-series). It powers `yosys` (synthesis) + `nextpnr-himbaechel`
(place & route) + its own `gowin_pack` / `gowin_unpack`.

Apicula 0.32 ships chipdbs for 10 devices — **GW1N-2 is not one of them.** The
IDCODE check is a hardcoded byte-match list in `apycula/bslib.py::read_bitstream`
(~lines 96–127). Our `0x0120681B` matches nothing → `ValueError("Unsupported
device")`, raised on the IDCODE *inside the bitstream*, **before** the `-d` flag's
database is even consulted. So this is genuine missing device coverage, not a
flag/config problem.

**Closest supported relative:** `GW1NZ-1`, IDCODE `0x0100681B`. Same `…681B` family
tail, one byte different. Fork point for our work.

## How the chipdb actually gets built

The naive mental model is "guess bytes until something works." The real method is
**differential fuzzing** — controlled experiments using the vendor tool as an oracle:

1. **Oracle = Gowin EDA.** It compiles HDL → bitstream. We never reverse the *tool*;
   we just run it thousands of times.
2. **One variable at a time.** Emit a minimal design that sets exactly one fabric
   feature — one LUT's truth table, one routing mux selection, one IO buffer enable.
   Compile it.
3. **Twin design.** Emit an identical design differing only in that one feature.
   Compile it.
4. **Diff the two bitstreams.** The bits that flipped *are* the bits controlling that
   feature. Record `bit position ↔ feature`.
5. **Sweep.** Repeat across every tile in the grid, every primitive, every routing
   resource. The accumulated map is the chipdb.

### The Gowin-specific shortcut

Apicula does **not** do this purely black-box. Gowin's IDE ships internal data files
— `.fse`, `.dat`, `.tm` — that already describe much of the fabric (tile layout,
wires, timing). Apicula **reverse-engineers the format of those files** (via
`apycula/fse_parser.py` + the chipdb builder) to extract most of the map for free,
then uses diff-fuzzing to confirm exact bit positions and fill gaps. So device
bring-up is more "parse the vendor's leaked map for this chip + verify" than
"fuzz from zero."

### Why it's per-device even within a family

Primitives are shared family-wide (a LUT4 is a LUT4 on every GW1N). What changes per
device is **geometry**: grid dimensions, where BRAM/PLL/IO blocks sit, and the
absolute bit positions. So GW1NZ-1 gets us the conceptual scaffolding and most
primitive definitions; the GW1N-2-specific effort is re-mapping positions for its
own grid. That's why "GW1NZ-1 is supported" helps a lot but isn't the finish line.

## Bottom-up bring-up order (the known recipe)

Mirrors IceStorm/Trellis/X-Ray and Apicula's own structure:

1. **Grid + IO** — tile dimensions, IO bank locations, pin → tile mapping.
2. **Logic primitives** — LUT truth-table bits, DFF config bits.
3. **Routing** — the mux configuration bits that connect wires between tiles.
4. **Hard blocks** — BRAM (incl. init-content layout), PLL config.
5. **Validate** — round-trip a few known designs through pack→unpack, then unpack
   the real `reference/` scope bitstream.

(GW1N-2 has no DSP, so that whole class of fuzzing is skipped — one fewer thing to map.)
