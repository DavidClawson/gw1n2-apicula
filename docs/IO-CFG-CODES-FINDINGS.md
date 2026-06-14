# GW1N-2 special-pin IO config codes — resolved (2026-06-13)

Closes backlog item A2 ("Map the ~10 `UNKNOWN_CFG_*` special-pin IO codes").

## Background
`apycula.chipdb.dat_fill_io_cfgs` labels each IOB with its dedicated special
function (clock input, PLL feedback, config-mode pin, …) via a per-pin integer
`cfg_code` read from the vendor `.dat` (`compat_dict['Cfg']` / `['SpecCfg']`).
The hand-maintained `_io_cfg` dict in `chipdb.py` turns each code into names.

For GW1N-2, ten codes weren't in `_io_cfg`, so PR3 made them non-fatal
`UNKNOWN_CFG_<n>` placeholders (a documented punt). The real build emits exactly
these ten:

```
43 @ IOR4A   44 @ IOR4B   45 @ IOR3A   46 @ IOR3B   75 @ IOL5A
136 @ IOR6B  141 @ IOB12A 153 @ IOR5B  154 @ IOR5A  160 @ IOR6A
```

## Method — cross-device vendor cross-reference (no oracle, no fuzzing)
`_io_cfg` is a **single global dict** shared by every non-GW5 device, which
means Gowin uses one consistent global enumeration of these codes. So a code
that is unlabelled on GW1N-2's tiny QFN48XF package is very often bonded out
*with* a package label on a larger package of another device.

`tools/m_iocfg_mine.py` reuses apicula's exact build path (monkeypatches
`dat_fill_io_cfgs`, aborts the slow tail with a sentinel) to record
`(device, pin, cfg_code, package_label)` for every IOB across the five minable
non-GW5 devices with vendor data installed: **GW1N-2, GW1NZ-1, GW1NS-4,
GW1N-9C, GW2A-18C**. It then inverts that to `cfg_code → {label}`.

**Validation:** the mined map reproduces the existing `_io_cfg` entries with
**27 agreements and 0 contradictions** (the rest of the known codes simply have
no bonded+labelled pin in this corpus). The method is therefore trustworthy.

## Resolved (5 of 10) — added to `_io_cfg`
Each was confirmed at a labelled pin on **two** independent vendor devices
(except 75, single source but unambiguous):

| code | GW1N-2 pin | name | evidence |
|------|-----------|------|----------|
| 75  | IOL5A | `LPLL_T_IN`   | GW1NS-4:IOT13A |
| 136 | IOR6B | `MCLK`, `D4`  | GW1NZ-1:IOR6D, GW1NS-4:IOT10A |
| 153 | IOR5B | `MO`, `D6`    | GW1NZ-1:IOR6B, GW1NS-4:IOT11A |
| 154 | IOR5A | `MI`, `D7`    | GW1NZ-1:IOR6A, GW1NS-4:IOT11B |
| 160 | IOR6A | `MCS_N`, `D5` | GW1NZ-1:IOR6C, GW1NS-4:IOT10B |

These are the **MSPI** master-flash-config quartet (MCLK/MCS_N/MI/MO) plus the
parallel-CPU-config data aliases D4–D7, and the left-PLL clock input — exactly
the kind of dedicated pins one expects on a right/left device edge.

Adding them globally is safe: a code in `_io_cfg` is only consulted when the
pin has *no* package label (the `bool(package_cfg) ^ bool(cfg_code)` XOR), which
for these codes is only the GW1N-2 case; on the devices that *do* bond them the
package label already wins.

Bonus corroboration: the same probe maps the JTAG quartet (TCK/TMS/TDO/TDI) to
IOT9A/B + IOT7A/B — independently matching the earlier R3 finding that GW1N-2
JTAG sits at IOT7/IOT9, not the QN48 datasheet pins.

## Stragglers (5 of 10) — left as honest `UNKNOWN_CFG`
`43 @ IOR4A, 44 @ IOR4B, 45 @ IOR3A, 46 @ IOR3B` (four adjacent right-edge pins)
and `141 @ IOB12A` carry **no package label on any device with vendor data
available here**, and aren't in the iotable CSVs or the binary `.ini`. Naming
them would be a guess, and per this project's standing rule ("a wrong map is
worse than none", from the PLL work) they remain non-fatal placeholders.

- They are all **unbonded on QFN48XF** → zero effect on decoding the scope
  bitstream (verified: scope unpack unchanged, 847 LUT4 / 192 ALU / 4 BSRAM /
  15 IDDRC / 1 ODDRC, same as before).
- Working hypothesis (unconfirmed): 43–46 sit immediately above the right-edge
  config/PLL pins (IOR5/IOR6) and may be right-PLL (RPLL) dedicated
  feedback/input pins specific to the GW1N-1P5C/2 die — which would explain why
  no other mined device, all with differently-placed PLLs, labels them.
- To finish them would need the GW1N-1P5C datasheet pin-description table or a
  dedicated Gowin pin-report; not worth blocking on.

## Result
- `UNKNOWN_CFG` warnings on the GW1N-2 build: **10 → 5**.
- Scope bitstream still unpacks cleanly (no regression).
- Tool: `tools/m_iocfg_mine.py`. Change: `_io_cfg` additions + refreshed
  fallback comment in `apycula/chipdb.py` (folded into PR3 / staged patch 03).

## Reproduce (on mars)
```bash
cd ~/gw1n2-apicula/tools/apicula && source .venv/bin/activate && source ../gowin-env.sh
python ~/gw1n2-apicula/tools/m_iocfg_mine.py        # mine + validate + resolve
python -m apycula.chipdb_builder GW1N-2 -o apycula/GW1N-2.msgpack.xz 2>&1 | grep -c "unknown pin"  # -> 5
```
