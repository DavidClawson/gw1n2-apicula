Adds the GW1N-2 device:

- `bslib.py`: recognize IDCODE `0x0120681B`.
- `chipdb_builder.py`: `DEVICE_PARAMS['GW1N-2']` (vendor device `GW1N-1P5C`, package
  `QFN48XF`, partnumber `GW1N-UV1P5QN48XFC7/I6`), `_chip_id`, GSR, and the Makefile
  target.
- `gowin_unpack.py`: package mapping.

`make apycula/GW1N-2.msgpack.xz` then builds a chipdb matching the datasheet
(19×20 grid, 2304 LUT4, 4 BSRAM, no DSP, 136 IOB).

The GW1N-2 die ships license-free only as GW1N-1P5C (same silicon — verified the
synth emits IDCODE `0x0120681B`), so the device intentionally points at GW1N-1P5C
vendor data.

Depends on #516 (partType-1 `.dat` support). Part of #515.
