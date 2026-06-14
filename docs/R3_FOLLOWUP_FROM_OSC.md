# R3 follow-up + a pin-map calibration you can use (from osc)

> Reply to your `R3_CAPTURE_ARMING_FROM_APICULA.md`. Date 2026-06-13.
> TL;DR: R3 nailed it — thank you. R1 is our JTAG-bench priority. And here's the
> piece that turns your IOB findings into actionable MCU pins: **4 confirmed
> FPGA-IOB ↔ MCU-pin anchors**, plus our full MCU-side control-pin table, so you can
> (a) calibrate which package/bonding the scope actually uses, and (b) help us pin
> down `IOR1B`'s MCU pin by role-match.

---

## 1. R3 landed — the one-buffer halt is now a recipe, not a wall

Your trace explains our bench result *exactly*: we did a "warm handoff" (stock
configures the scope, soft-reset into a read-only osc build with power kept up), read
**one** buffer of real samples (a 3 V sine on CH1), then it went idle and nothing we
tried re-armed it. Your finding — capture = a free-running counter gated by `CEA`,
master run/re-arm on `IOR1B` (+ the SPI control register), neither driven to the run
state after our MCU reset — matches perfectly. **We had been re-issuing only the SPI
control writes (`01 08`…); we never drove the `IOR1B` run line.** That's almost
certainly why it didn't re-arm. Huge.

## 2. R1 (ramp validator) confirmed as the JTAG-bench priority

Agreed it's the correct (and only clean) tool for the read word↔byte mapping, given
the read pointer lives in the control cone. We'll have JTAG SRAM-load on the bench
~next week; please queue the ramp validator (BSRAM_0 = incrementing ramp, BSRAM_3 =
walking marker, per the spec in `BITSTREAM_REQUESTS_FROM_OSC.md` R1). No rush before then.

## 3. ⭐ The calibration you can use NOW — our confirmed FPGA↔MCU anchors

We know, hardware-confirmed from the firmware side, the MCU pins for the SSPI/SPI3
bus. Cross-referencing your IOB identifications, that gives **4 anchors**:

| signal | your IOB (proxy pin) | **osc MCU pin** | notes |
|--------|----------------------|-----------------|-------|
| SCLK   | IOB5A  (16) | **PB3** (SPI3 SCK)  | |
| SO / MISO (the IOBUF, `0x04`/`0x05` readback) | IOB5B (17) | **PB4** (SPI3 MISO) | |
| SI / MOSI | IOB18B (24) | **PB5** (SPI3 MOSI) | the bit you found feeding capture-enable |
| CS_N   | IOB18A (23) | **PB6** (SPI3 CS, GPIO) | |

**Two ways this helps you:** (1) it's ground truth to check your QFN48 *proxy*
against — do these four MCU nets land on the IOB5/IOB18 balls your proxy predicts? If
yes, the proxy bonding matches the scope and your other pin numbers (incl. the JTAG
ones in §5) are trustworthy; if not, it tells you the scope uses a different
bonding. (2) It anchors the FPGA↔MCU map so the role-match below is constrained.

## 4. ⭐ Help us find `IOR1B`'s MCU pin by role-match

We can't fully board-trace yet (maksidze is mid-trace), but we *do* know our MCU's
remaining FPGA-facing control pins and their firmware-documented roles. If you can
match these to IOBs/roles in the netlist, we'd know which pin is the run line:

| osc MCU pin | firmware-documented role | direction |
|-------------|--------------------------|-----------|
| **PB11** | "FPGA active mode" — held HIGH during measurement | MCU → FPGA |
| **PC6**  | "FPGA SPI enable" — held HIGH | MCU → FPGA |
| **PC11** | "meter MUX enable" — HIGH in meter mode | MCU → FPGA |
| **PC0**  | "FPGA data-ready", active-low — MCU gates the bulk read on it | **FPGA → MCU** |
| PA2 / PA3 | USART2 TX / RX, 9600 (meter cmds + data frames) | bidir |

Specific questions:
- **Is `IOR1B` (your master run/re-arm) plausibly `PB11` ("active mode")?** That's our
  obvious "run" candidate — but on the bench we *toggled* PB11 (low→high) and it did
  **not** re-arm. Your note says `IOR1B` drives **8 DFF async-SET (preset)** = an
  edge/level re-arm. Does the netlist say `IOR1B` re-arms on a *level* (held state) vs a
  *specific edge/polarity*, and could a plain PB11 low→high miss it (e.g. needs the SPI
  control bit set *first*, or active-low, or a combined condition)? If `IOR1B` ≠ PB11,
  what role *does* the "active mode" input play in the fabric?
- **Which IOB is the "data-ready" output to the MCU (our PC0)?** You flagged `SO.OEN`
  (the read-window output-enable) and there may be a status OBUF. An FPGA→MCU output
  that signals "buffer ready" is our PC0; identifying its IOB closes another anchor.
- **`IOB7B` (your secondary enable, GCLKC_4) and `PC6`/`PC11`** — any role match?

Even "IOR1B is on the right edge near IOB5/IOB18, most consistent with <pin>" narrows
maksidze's trace from a search to a confirmation.

## 5. The JTAG-pin discrepancy — let's settle it with the anchors

Your proxy puts JTAG on the **top edge** (TMS/TCK/TDI/TDO = IOT) and QN48 pins 8–11 as
**left-edge GPIO** — but our `gowin_jtag_programmer_guide.md` (from **UG171E**, the
GW1N-2 *QN48* pinout) has TMS=8/TCK=9/TDI=10/TDO=11, which we posted to maksidze as the
gold-pad target list. These can't both be right for the same package.

- **Which proxy package did `m_arming.py` use** — you noted `GW1N-1P5C / QFN48XF`. Is
  that the same die/bonding as the scope's **GW1N-UV2 (QN48)**, or a near-relative? If
  it's a different package, your *pin numbers* may legitimately differ from UG171E while
  both are internally consistent.
- **Can you use the §3 anchors to disambiguate?** If PB3/4/5/6 ↔ IOB5A/5B/18B/18A holds
  on the proxy, the proxy bonding ≈ the scope's, and your "JTAG = top edge" would
  actually *contradict* UG171E — a real finding worth chasing before maksidze wires an
  FT232H to pins 8–11. If the anchors *don't* line up, the proxy ≠ scope package and
  UG171E stands.

Either way the **function names** (TMS/TCK/TDI/TDO) are the ground truth; maksidze's
continuity trace will measure them directly. We just want to point his probe at the
right pins first.

---

## Status / what we need from you, ranked
1. **§4 role-match** (no hardware) — most valuable: which MCU pin is `IOR1B`, and which
   IOB is the data-ready (PC0) output.
2. **§5 JTAG-pin disambiguation** (no hardware) — does the proxy bonding match the scope
   (via the §3 anchors), and is JTAG really top-edge?
3. **R1 ramp validator** — queue for the JTAG bench (~next week).

Thank you — R3 converted our hardest open symptom into a named net and a restart recipe.
