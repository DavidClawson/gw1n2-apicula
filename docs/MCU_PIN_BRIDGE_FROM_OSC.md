# MCU-pin bridge for your R3 arming finding (from osc/ripcord, 2026-06-13)

Your `R3-CAPTURE-ARMING-FINDINGS.md` identified the capture run/re-arm + readback inputs by
**FPGA pad** (`IOR1B` pin35 run/re-arm, `IOB7B` pin19, `SI`=IOB18B pin24, `SO`=IOB5B pin17,
`SCLK`=IOB5A pin16, `CS_N`=IOB18A pin23). We bridged those to the **MCU pins** using osc's
`HARDWARE_PINOUT.md` + ripcord's execution-verified SPI3 decode.

**Full write-up (authoritative):**
`osc/reverse_engineering/analysis_v120/mcu_fpga_boundary_reconcile_2026-06-13.md`

**TL;DR for this project:**
- The MCU "SPI3" bus = your SSPI port repurposed: **PB3→SCLK(IOB5A), PB5→SI(IOB18B),
  PB4→SO(IOB5B), PB6→CS_N(IOB18A)** (function-match, high confidence).
- Your `SO`-is-the-only-IOBUF + OEN-gated-by-read-window finding **explains osc's silicon
  "MISO inert"**: the counter halts when run/re-arm isn't driven → SO.OEN never asserts.
- **Run/re-arm (`IOR1B`) ← MCU PB11** ("FPGA active mode") is our ranked hypothesis;
  `IOB7B ← PC6` ("FPGA SPI enable"). Bench test in §5 of the full note will confirm or swap.
- If neither PB11 nor PC6 arms it, the run line is one of the **unbonded top-edge IOT pads**
  your proxy package can't number — that would need a board trace.

No action needed from apicula unless the bench test (osc side) comes back negative, in which
case we'll ask you to re-trace `IOR1B`'s fan-out for an alternate run-control candidate.
