#!/usr/bin/env python3
"""M5 recon: understand the scope .bin layout vs the chipdb's cmd_hdr/cmd_ftr so
the binary->.fs converter can re-insert newlines at the right byte offsets.

Apicula's write_bitstream lays the stream out as (uncompressed):
    <each cmd in db.cmd_hdr on its own line>
    <each frame: frame_bytes + 2 CRC + 6 bytes 0xff>   x n_frames
    <ftr[0]>, [slots/bsram], <ftr[1:]>
The raw .bin is exactly those bytes with no newlines.
"""
import os, sys
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools"))
from apycula.chipdb import load_chipdb

DB = os.path.expanduser("~/gw1n2-apicula/tools/apicula/apycula/GW1N-2.msgpack.xz")
BIN = os.path.expanduser("~/m5/scope_bitstream_2c53t_v120.bin")

db = load_chipdb(DB)
hdr = db.cmd_hdr
ftr = db.cmd_ftr
print("=== cmd_hdr ===", len(hdr), "commands")
for i, c in enumerate(hdr):
    print(f"  hdr[{i}] len={len(bytes(c))}: {bytes(c).hex()}")
print("=== cmd_ftr ===", len(ftr), "commands")
for i, c in enumerate(ftr):
    print(f"  ftr[{i}] len={len(bytes(c))}: {bytes(c).hex()}")

b = open(BIN, "rb").read()
print(f"\n=== scope .bin: {len(b)} bytes ===")
print("  head:", b[:0x48].hex())
print("  tail:", b[-0x30:].hex())

# Find sync a5c3
sync = b.find(b"\xa5\xc3")
print(f"  sync a5c3 at {sync:#x}")
# frame count command 0x3b
i3b = b.find(b"\x3b\x80")
print(f"  0x3b80 frame-count cmd at {i3b:#x}: {b[i3b:i3b+4].hex()} -> frames={int.from_bytes(b[i3b+2:i3b+4],'big')}")

# how many header bytes precede the first frame? header = up to and including the
# 0x3b command (4 bytes). Sum cmd_hdr lengths for comparison.
hdr_bytes = sum(len(bytes(c)) for c in hdr)
ftr_bytes = sum(len(bytes(c)) for c in ftr)
n = int.from_bytes(b[i3b+2:i3b+4], "big")
print(f"\n  sum(cmd_hdr)={hdr_bytes}  sum(cmd_ftr)={ftr_bytes}  frames={n}")
# solve frame stride: (total - hdr - ftr) / frames  (each frame = data+2+6)
remain = len(b) - hdr_bytes - ftr_bytes
print(f"  (len - hdr - ftr) = {remain};  /frames = {remain/n if n else 0}")
print(f"  => frame stride bytes ~ {remain//n if n else 0}; frame_data = stride-8 = {remain//n-8 if n else 0}")
# device grid for sanity (frame width relates to columns)
print(f"  device rows={db.rows} cols={db.cols}  (grid {len(db.grid)}x{len(db.grid[0])})")
