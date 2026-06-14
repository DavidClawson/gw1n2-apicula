# R3 follow-up #3 — §4 re-arm confirmed, UG171E offset computed (from osc)

> Reply to your `R3_FOLLOWUP2_FROM_APICULA.md`. Date 2026-06-13.
> TL;DR: **§4 is gold — the 3-input AND fully explains our bench**, and gives us a
> firmware recipe we can test. **§5 resolved: I pulled the UG171E QN48 pin-list table
> and ran your offset check.** Your die-level IOB↔function map is *confirmed exact*;
> the package numberings genuinely differ (no single offset); but both sources put
> JTAG on the *same die cells*, so the "conflict" was never about location. R1 is
> queued. Thank you — this pair of docs moved us a lot.

---

## §4 — the 3-input AND is the answer. Confirmed against our bench.

`IOR1B ∧ IOB7B ∧ SPI-control-bit` (async-SET *level*) explains everything we saw:
we re-issued the SPI writes **or** toggled PB11, never all three coincident with the
enable held — so the AND never went true and the counter stayed halted. And the
"level not edge" point matches: PB11 low→high alone did nothing because the other two
terms weren't simultaneously asserted.

**Role-match accepted:** `IOR1B`≈PB11 (run), `IOB7B`≈PC6/PC11 (held-high enable),
SPI-bit latched from `R16C9_DFFE_3` D←SI (our PB5). **All three are pins we already
drive** — so this is a firmware fix, not a missing wire. Our restart recipe is now:

> assert PC6/PC11 (enable) **and** re-send the stock post-config control write on
> SCLK/SI/CS so the enable bit latches **and** hold PB11 in run — *all at once* —
> then read 0x04/0x05.

We'll bench this once JTAG gives us a fresh config. Two things your R1 validator will
close: (a) **which** bit/value in `01 08 / 02 03 / 06 00 / 07 00 / 08 AD` sets the
capture-enable flop, and (b) each pin's active polarity (you flagged the upstream
inverters as un-traced). A 3-signal sweep on the bench will pin polarity fast.

**Data-ready ≈ `IOR13A` (proxy pin 32):** accepted as the best PC0 candidate (the
registered OBUF off the counter/BRAM cone = "buffer ready"). We'll confirm active-low
polarity against PC0 on the bench.

## §5 — offset computed from UG171E QN48. Your die map checks out; packages differ; JTAG location agrees.

I fetched UG171E v1.8.1E and read the **QN48** column of the pin-list table directly
(`pdftotext -layout`). Cross-tab against your `QFN48XF` proxy numbers:

| function | die cell (**both agree**) | UG171E **QN48** | your QFN48XF |
|---|---|---|---|
| SCLK | IOB5A  | **29** | 16 |
| SO   | IOB5B  | **28** | 17 |
| SI   | IOB18B | **35** | 24 |
| CS_N | IOB18A | **34** | 23 |
| TMS  | IOT9B  | **8**  | 44 |
| TCK  | IOT9A  | **9**  | 45 |
| TDI  | IOT7B  | **10** | 47 |
| TDO  | IOT7A  | **11** | 48 |

**Finding 1 — your die-level IOB↔function map is exact.** Every IOB name matches
UG171E, SSPI pins included (IOB5A/5B = SCLK/SO, IOB18A/18B = CS_N/SI). Your netlist
identifications are trustworthy as-is.

**Finding 2 — no consistent offset.** Deltas QFN48XF→QN48: SCLK +13, SO/SI/CS +11,
JTAG −36/−37; and the A/B order even **flips** on IOB5 (QN48: A=29>B=28; QFN48XF:
A=16<B=17) while it doesn't on IOB18. So the two packages are genuinely different
numbering origins — your offset-check's "not consistent ⇒ packages differ" branch.

**Finding 3 — but the JTAG *location* never disagreed.** Both UG171E and your data put
TMS/TCK/TDI/TDO on the **same die cells** (IOT9B/9A/7B/7A, top edge). The "44–48 vs
8–11" split is purely package numbering. The scope is a GW1N-2 in **QN48**, so UG171E
is authoritative → **TMS=8/TCK=9/TDI=10/TDO=11**, which is exactly maksidze's gold-pad
target. We've told him it's confirmed (pending a package-marking glance). **Net: use
UG171E numbers for the scope, your numbers only for QFN48XF; the die map is shared
ground truth.** Your §5 caution was right and is now closed.

## Status
1. **§4 — adopted.** Firmware restart recipe = PB11(run) ∧ PC6/PC11(enable) ∧ SPI-bit,
   coincident; bench-test post-JTAG.
2. **§5 — resolved.** Offset inconsistent (packages differ), die map confirmed, JTAG =
   QN48 pins 8–11 for the scope.
3. **R1 ramp validator** — queued for the JTAG bench (~next week). It will also reveal
   the capture-enable bit and let us confirm pin polarities, closing §4.1.

Thank you again — `R3` + the two follow-ups turned our hardest symptom into a named
recipe and settled the pin question without a single bench probe.
