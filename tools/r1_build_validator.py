#!/usr/bin/env python3
"""R1 scope-readout validator builder (osc request).

Takes the stock GW1N-2 bitstream and overwrites ONLY the (currently all-zero) BRAM
initialization region so the four sample BRAMs hold a known, self-describing pattern:
  BSRAM_0 (CH1, grid R10C2  / col 1 ) = byte ramp   : byte address A -> A & 0xFF
  BSRAM_3 (CH2, grid R10C17 / col 16) = walking mark : 0xA5,0x5A,0xA5,0x5A,...
BSRAM_1/2 left zero. The entire stock logic+routing (incl. the 0x04/0x05 SPI readout
path) is preserved byte-for-byte, so osc's existing firmware reads it unchanged and the
returned sequence reveals the readout's word/byte ordering.

Method: apicula's own store_bsram_init_val() is the forward encoder (guaranteed correct);
we add an inverse decoder, round-trip-verify the two on a known pattern, then graft and
re-emit via bslib.write_bitstream() (handles frame CRCs). No hardware / no Gowin oracle.

Run on mars:  ~/gw1n2-apicula/tools/apicula/.venv/bin/python r1_build_validator.py
"""
import sys, os
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools/apicula"))
from apycula import bslib, chipdb
import apycula.bitmatrix as bm
from apycula import gowin_pack as gp
import lzma, msgspec

FAM = "GW1N-2"
STOCK = os.path.expanduser("~/r1_build/scope.fs")
OUT   = os.path.expanduser("~/r1_build/scope_R1_validator.fs")

# --- load chipdb (same path apicula uses) ---
import importlib.resources
with importlib.resources.path('apycula', f'{FAM}.msgpack.xz') as p:
    db = msgspec.msgpack.decode(lzma.open(str(p)).read(), type=chipdb.Device)
gp.db = db
gp.device = FAM
print(f"db loaded: simplio_rows={sorted(db.simplio_rows)}  width={db.width}")

# ---------- INIT_RAM construction (width=256 / 16-bit words, parity skipped) ----------
WIDTH = 256
NROWS = 0x40           # 64 init rows
# replay get_bits to learn, for each row, which string positions hold data bits and in
# what global data-bit address order (addr) + bit_no. This mirrors store_bsram_init_val.
def walk():
    """yield (init_row, str_index, addr, bit_no) for every DATA bit, in encoder order."""
    addr = -1
    for init_row in range(NROWS):
        bit_no = 0; ptr = -1
        # we emit string of length WIDTH; str_index is the python index = WIDTH+ptr
        while ptr >= -WIDTH:
            if bit_no == 8 or bit_no == 17:
                # width==256 -> inserted '0', ptr not consumed, addr unchanged
                bit_no = (bit_no + 1) % 18
            else:
                addr += 1
                yield (init_row, WIDTH + ptr, addr, bit_no)
                ptr -= 1
                bit_no = (bit_no + 1) % 18

# precompute the walk once
WALK = list(walk())
NDATA = len(WALK)
print(f"data bits per BRAM: {NDATA} (= {NDATA//8} bytes, {NDATA} of {NROWS*WIDTH})")

def make_init_ram(byte_fn):
    """byte_fn(byte_index)->0..255 ; returns dict INIT_RAM_xx -> bitstring (LSB-first per byte)."""
    rows = [['0'] * WIDTH for _ in range(NROWS)]
    for (init_row, sidx, addr, bit_no) in WALK:
        byte_i = addr // 8
        bitpos = addr % 8                      # LSB-first within the byte
        val = (byte_fn(byte_i) >> bitpos) & 1
        rows[init_row][sidx] = '1' if val else '0'
    return {f'INIT_RAM_{r:02X}': ''.join(rows[r]) for r in range(NROWS)}

ramp_parms   = make_init_ram(lambda k: k & 0xFF)
marker_parms = make_init_ram(lambda k: 0xA5 if (k & 1) == 0 else 0x5A)
ATTRS = {'BSRAM_SUBTYPE': ''}   # blank subtype -> WIDTH 256 path

# ---------- encoder (apicula) wrapper: returns the (256 x db.width) map for one BRAM ----------
def encode_one(row, col, parms):
    gp.bsram_init_map = None
    gp.store_bsram_init_val(db, row, col, 'BSRAM', dict(parms), dict(ATTRS))
    return gp.bsram_init_map   # (256*len(simplio_rows)) x db.width, only this BRAM's cols set

# ---------- inverse decoder: map region -> recovered byte array ----------
def decode_one(region, row, col):
    """region = (256*nsimpl x width) bitmatrix; return list[byte] for BRAM at (row,col)."""
    # reproduce store_bsram_init_val's placement math to know (y,x) and undo flipud
    height = 256
    y = 0
    for brow in sorted(db.simplio_rows):
        if row == brow: break
        y += height
    x = 0
    for jdx in range(col):
        x += db[0, jdx].width
    # loc_map (256 x 180) = flipud( region[y:y+256, x:x+180] )
    sub = [region[y + i][x:x + 180] for i in range(256)]
    loc_map = list(reversed(sub))
    rev = db.rev_logicinfo('BSRAM_INIT')
    bytes_out = [0] * (NDATA // 8)
    for (init_row, sidx, addr, bit_no) in WALK:
        logic_line = bit_no * 4 + (addr >> 12)
        bit = rev[logic_line][0] - 1
        quad = {0x30: 0xc0, 0x20: 0x40, 0x10: 0x80, 0x00: 0x00}[addr & 0x30]
        map_row = quad + ((addr >> 6) & 0x3f)
        v = loc_map[map_row][bit]
        if v:
            bytes_out[addr // 8] |= (1 << (addr % 8))
    return bytes_out

# ---------- 1. round-trip verify encoder<->decoder on the ramp ----------
m = encode_one(9, 1, ramp_parms)
rec = decode_one(m, 9, 1)
exp = [(k & 0xFF) for k in range(NDATA // 8)]
assert rec == exp, f"ROUND-TRIP FAIL: {rec[:8]} vs {exp[:8]}"
print(f"[ok] encoder<->decoder round-trip on ramp: first16={rec[:16]}")

# ---------- 2. graft into stock ----------
bs, hdr, ftr, slots = bslib.read_bitstream(STOCK)
rows, cols = bm.shape(bs)
assert (rows, cols) == (722, db.width), (rows, cols)
INIT0 = rows - 256

m_ramp   = encode_one(9, 1,  ramp_parms)     # BSRAM_0 / CH1
m_marker = encode_one(9, 16, marker_parms)   # BSRAM_3 / CH2
# OR the two maps together (different column ranges, no overlap) into stock's init rows
for i in range(256):
    for xx in range(cols):
        v = m_ramp[i][xx] | m_marker[i][xx]
        if v:
            bs[INIT0 + i][xx] = v
ones = sum(sum(bs[INIT0 + i]) for i in range(256))
print(f"[ok] grafted; init-region ones now: {ones} (was 0)")

# ---------- 3. emit ----------
bslib.write_bitstream(OUT, bs, hdr, ftr, False, slots)
print(f"[ok] wrote {OUT}")

# ---------- 4. re-read & verify CRCs + decode back ----------
bs2, h2, f2, s2 = bslib.read_bitstream(OUT)           # read_bitstream asserts CRCs
r2, c2 = bm.shape(bs2)
assert (r2, c2) == (722, db.width), (r2, c2)
region = [bs2[INIT0 + i] for i in range(256)]
ch1 = decode_one(region, 9, 1)
ch2 = decode_one(region, 9, 16)
print(f"[verify] re-read OK ({r2}x{c2}), CRCs pass")
print(f"[verify] CH1 (BSRAM_0) first 16 bytes: {[hex(b) for b in ch1[:16]]}")
print(f"[verify] CH1 bytes 252..260         : {[hex(b) for b in ch1[252:260]]}  (wrap at 256)")
print(f"[verify] CH2 (BSRAM_3) first 16 bytes: {[hex(b) for b in ch2[:16]]}")
assert ch1[:16] == list(range(16)), ch1[:16]
assert ch1[255] == 255 and ch1[256] == 0, (ch1[255], ch1[256])
assert all(ch2[k] == (0xA5 if k % 2 == 0 else 0x5A) for k in range(16)), ch2[:16]
print("\n*** R1 validator built and verified ***")
