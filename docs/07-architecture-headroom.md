# 07 — Scope design: headroom & architecture notes

> From analyzing the unpacked stock bitstream (`tools/m5/scope_unpacked.v`) against
> the GW1N-2 chipdb. Tools: `tools/m_analyze.py`, `tools/m_clocks.py`. 2026-06-13.
> Caveat: this is the *fabric* netlist (gate-level: LUT INIT masks, FFs, routing),
> not RTL — utilization/placement is reliable; "what each block does" is not yet RE'd.

## Resource utilization / headroom
| resource | used | capacity | headroom |
|---|---|---|---|
| Logic (LUT4 + ALU) | 1039 (847 LUT4 + 192 ALU) | 2304 LUT slots | **~55% free** |
| Flip-flops | ~879 (DFFE/RE/CE/PE) | 1728 | **~49% free** |
| Block RAM (BSRAM) | 4 | 4 | **0% free (full)** |
| PLL | 1 | 1 | **0% free (full)** |
| DDR I/O (IDDRC/ODDRC) | 16 | — | both die edges used |

**Takeaway:** lots of room for added *logic* (comparators, triggers, counters,
state machines) and registers, but **BRAM and the PLL are maxed** — any feature
needing another sample buffer or a new synthesized clock is constrained.

## Spatial layout
Logic fills most of the array except the architectural **center row (row 10,
0-indexed 9)** which carries the clock spine and holds no CLS — so the apparent
"top block / bottom block" split is the clock row, not necessarily two functions.
Mass is ~balanced: top 1581 / bottom 1633 placed cells.

DDR input cells (IDDRC) sit on **both** the left (col 1) and right (col 20) edges —
consistent with two independent high-speed acquisition front-ends.

## Clock domains
Three primary clock domains feed the real flip-flops:
- `CLK0` 313 FFs, `CLK1` 292 FFs, `CLK2` 274 FFs.
- **All three span the whole die** (rows 3–17, cols 2–19) and split ~evenly
  top/bottom — i.e. the domains are *interleaved*, not regionally separated.

## On the "scope + DMM, side by side" hypothesis
- **Consistent with it:** dual-edge DDR front-ends; ~50% utilization (room for two
  functions in one bitstream); a single 115 KB bitstream matches the typical
  cost-optimized 2-in-1 architecture (one FPGA image, firmware selects the mode).
- **Not (yet) shown:** the two functions are *not* placed in separate regions —
  the placer interleaved everything, and the 3 clock domains are mixed across the
  fabric. So spatial/clock analysis can't by itself confirm two independent blocks.
- **Decisive test (TODO):** trace the two data paths — from each DDR-input group,
  follow the pipeline to the BRAMs and the output/control pins, and see whether the
  netlist splits into two weakly-connected sub-graphs. Needs connectivity tracing
  that resolves Apicula's node aliases (the routing-decode caveat from M3).

## Data-path trace — the design is FOUR independent channels (2026-06-13)
`tools/m_datapath.py`: dataflow graph (routing + bel input→output edges) with
high-fanout global nets (>24 sinks: clocks/resets/enables) excluded so the trace
follows real data.

- **The two edge ADC front-ends feed completely disjoint paths.** Forward-BFS from
  the left-edge IDDRC outputs reaches 157 nets; from the right-edge IDDRC outputs,
  157 nets; **overlap = 0**. Left ADC → **BSRAM_0**, right ADC → **BSRAM_3**.
- **All four BRAMs are independent.** Backward source cones are ~98 nets each with
  **zero pairwise overlap** — four isolated capture/storage paths in one bitstream.

**Interpretation:** this strongly supports the "multiple independent functions side
by side" hypothesis — refined to **≥4 independent channels** (2 clearly ADC-driven).
For the 2-channel scope + DMM device, the natural reading is 2 analog scope channels
(each ADC→its own BRAM) plus additional independent paths (DMM / processed or
double-buffered streams) on the other two BRAMs. Confirming the exact role of each
channel (and where the DMM sits) is the next RE step.

**For feature-adding (Tier 1):** the channels have clean, identifiable boundaries —
the ADC sample bus is the set of IDDRC output nets per edge, and each channel's
cone is small (~100-160 nets). A trigger could tap a channel's ADC nets and add a
comparator in the free fabric without touching the rest of the design.

## FPGA external interface map (2026-06-13, tools/m_interface.py)
I/O cells by die edge:
- **LEFT (col 1):** 16 IDDRC (fast ADC in) + **3 ODDRC (fast OUT = DAC / sig-gen)** + 9 IBUF + 1 OBUF
- **RIGHT (col 20):** 14 IDDRC (fast ADC in) + 8 IBUF + 2 OBUF
- **TOP (row 1):** 34 IBUF — a large input group = almost certainly the **MCU control/data bus**
- **BOT:** 4 IBUF + 1 IOBUF (bidirectional)

Channel ↔ front-end (forward trace):
- **BSRAM_0 ← LEFT-edge ADCs** (IDDRC R6C1/R11C1/R15C1/R17C1) = one scope channel
- **BSRAM_3 ← RIGHT-edge ADCs** (IDDRC R3C20/R5C20/R11C20/R13C20) = the other scope channel
- **ODDRC (R5C1, left) → no BRAM** = an output generator → **signal generator / DAC**
- **BSRAM_1, BSRAM_2:** independent cones, no fast-ADC source → candidates for the
  **DMM** and/or processed/secondary streams.

So the 4 independent blocks line up with the user's guess: 2 scope channels + a
signal generator (ODDRC) + a DMM. The ~34 top-edge inputs are the MCU interface; the
scope enable/arming + readout are driven over that bus (the control nets are
high-fanout, which is why they're excluded from the dataflow cones). The exact
scope-enable bits and the BRAM→MCU readout path are the next RE targets — and are
the FPGA-side of the "custom firmware can do DMM but not scope" problem.

## Scope bitstream header decode + dual-bitstream model (2026-06-13)
Working model (from the firmware/hardware side): the FPGA's **internal flash holds a
DMM-only image** that self-loads at power-up (instant-on); switching to scope mode,
the **MCU streams the fuller scope bitstream** (the `.bin` we've analyzed) into the
FPGA to reconfigure it. The scope image contains 2 scope channels + a (redundant)
**DMM** + the **signal generator** — which matches our 4-independent-block finding
exactly. So our analysis is of the *MCU-loaded scope image*, and it's consistent.

Header decode of `scope_bitstream_2c53t_v120.bin` (per apicula `doc/commandstructure.md`):
- `06 00000000 0120681b` — IDCODE check = 0x0120681B (GW1N-2) ✓
- `10 00000000 00 0000` — config options: uncompressed, program_done_bypass off,
  loading_rate byte = 0x00
- `51 00 ffffffffffff` — uncompressed (no compression keys)
- `0b 000000` — **bit_security SET** (this command only appears when security is on)
- `d2 00ffff 00000000` — SPI-flash address = 0 (not loading from external SPI flash)
- `12 000000` — config command
- `3b 80 02d2` — **bit_crc_check SET**, 722 config frames

Implications for "custom firmware does DMM but not scope":
- DMM working ⇒ the NV-flash DMM image boots fine; the MCU↔FPGA bus works.
- Scope failing ⇒ the MCU's job of **reconfiguring the FPGA with the scope image**
  is what's failing — a bitstream-*loading* problem, not a register-init problem.
- We **proved every frame CRC validates** (M5), so the `.bin` blob is intact and
  complete. If the FPGA rejects it, the fault is in the *streaming/reconfig protocol*
  (SSPI/JTAG sequence, RECONFIG_N / mode pins, clocking/byte order), not the data.
- Security + CRC-check are ON — relevant to load/readback behavior.
