Adds the Gowin GW1N-2 to the Himbächel-Gowin uarch. Pairs with apicula GW1N-2
support (YosysHQ/apicula — partType-1 `.dat`, device recognition, pinout/IO).

- `himbaechel/uarch/gowin/CMakeLists.txt`: add `GW1N-2` to
  `ALL_HIMBAECHEL_GOWIN_DEVICES` so the build generates `chipdb-GW1N-2.bin`.
- `himbaechel/uarch/gowin/gowin_arch_gen.py`:
  - add `GW1N-2` to the `simple_io` set (the GW1N-1P5C die shares the small-part IO
    layout with GW1NZ-1 / GW1N-1);
  - in `create_pll_tiletype`, emit the PLL tile without a PLL bel when the chipdb has
    no `RPLLA`. The GW1N-2 rPLL isn't decoded yet on the apicula side (its portmap
    lives in the partType-1 extended table, and the license-free GW1N-1P5C proxy
    exposes no rPLL synthesis resource to fuzz against), so the chipdb has no PLL bel
    for now — this keeps logic/routing/IO designs building. To be removed once
    apicula's rPLL lands.

No `gowin.cc` change is needed: the GW1N-1P5C partnumber is selected with
`--vopt family=GW1N-2`, the same idiom the examples already use for GW1N-9C / GW2A.

Example lives in apicula `examples/gw1n2/` (a blinky); the `toolchain.yml` matrix
gets a `{target: gw1n2, dir: examples/gw1n2}` entry once this lands and apicula's
pinned nextpnr commit is bumped. Built and round-tripped the blinky through a
from-source build with `-DHIMBAECHEL_GOWIN_DEVICES="GW1N-2"` (0 errors;
`blinky-gw1n2.fs` has sync `0xA5C3` and unpacks back cleanly).

**Note on the device/part:** the GW1N-2 die ships license-free only as GW1N-1P5C, so
the device data and example partnumber are GW1N-1P5C. Open to guidance on the
preferred device/package naming.
