#!/usr/bin/env python3
"""Inverse of gowin_pack.store_bsram_init_val — decode BSRAM init contents from a
bitstream's appended init region back into INIT_RAM_xx parameters.

This is the basis for an upstream gowin_unpack feature (gowin_unpack currently emits
BSRAM bels + config but NOT memory contents). The bit-mapping below is a single source
of truth shared by encode and decode, so they are exact inverses by construction.

Self-test (run on mars, apicula venv): drives apicula's real store_bsram_init_val as the
ground-truth encoder for width 256 and 288 and asserts the decoder recovers the input.
    ~/gw1n2-apicula/tools/apicula/.venv/bin/python bsram_init_decode.py GW1N-2
"""
import sys, os
sys.path.insert(0, os.path.expanduser("~/gw1n2-apicula/tools/apicula"))

_QUAD = {0x30: 0xc0, 0x20: 0x40, 0x10: 0x80, 0x00: 0x00}

def bsram_bit_map(db, width):
    """Return [(init_row, str_index, map_row, bit)] for every STORED init bit, mirroring
    store_bsram_init_val's get_bits()/addr walk exactly. width: 256 (no subtype) or 288 (X9)."""
    rev = db.rev_logicinfo('BSRAM_INIT')
    out = []
    addr = -1
    for init_row in range(0x40):
        bit_no = 0
        ptr = -1
        while ptr >= -width:
            if bit_no == 8 or bit_no == 17:
                if width == 288:                       # parity bit IS stored in 288 mode
                    sidx = width + ptr
                    logic_line = bit_no * 4 + (addr >> 12)
                    bit = rev[logic_line][0] - 1
                    map_row = _QUAD[addr & 0x30] + ((addr >> 6) & 0x3f)
                    out.append((init_row, sidx, map_row, bit))
                    ptr -= 1
                # width==256: parity forced '0', not stored, addr/ptr unchanged
                bit_no = (bit_no + 1) % 18
            else:
                addr += 1
                sidx = width + ptr
                logic_line = bit_no * 4 + (addr >> 12)
                bit = rev[logic_line][0] - 1
                map_row = _QUAD[addr & 0x30] + ((addr >> 6) & 0x3f)
                out.append((init_row, sidx, map_row, bit))
                ptr -= 1
                bit_no = (bit_no + 1) % 18
    return out

def _placement(db, row, col, height=256):
    """(y, x) of a BSRAM's loc_map block in the global bsram_init_map (non-GW5A)."""
    y = 0
    for brow in sorted(db.simplio_rows):
        if row == brow:
            break
        y += height
    x = 0
    for jdx in range(col):
        x += db[0, jdx].width
    return y, x

def decode_bsram_init(db, region, row, col, width=256):
    """region = the appended BRAM-init bitmatrix (256*nsimpl rows x dev width).
    Returns {INIT_RAM_xx: bitstring} for the BSRAM at grid (row, col)."""
    import apycula.bitmatrix as bm
    y, x = _placement(db, row, col)
    # loc_map (256 x 180) = flipud(region[y:y+256, x:x+180])   (undoes the encoder's flipud)
    sub = [region[y + i][x:x + 180] for i in range(256)]
    loc_map = list(reversed(sub))
    rows = [['0'] * width for _ in range(0x40)]
    for (init_row, sidx, map_row, bit) in bsram_bit_map(db, width):
        if loc_map[map_row][bit]:
            rows[init_row][sidx] = '1'
    return {f'INIT_RAM_{r:02X}': ''.join(rows[r]) for r in range(0x40)}


def bram_tiles(db):
    """grid (row,col) of every BSRAM main tile (has a 'BSRAM' bel)."""
    return [(r, c) for r in range(db.rows) for c in range(db.cols)
            if 'BSRAM' in db[r, c].bels]

def init_region(db, bitmap):
    """The appended BRAM-init region (or None if the bitstream has no bsram init)."""
    import apycula.bitmatrix as bm
    grid_h = sum(db[r, 0].height for r in range(db.rows))
    total = bm.shape(bitmap)[0]
    region_rows = 256 * len(db.simplio_rows)
    if total < grid_h + region_rows:
        return None
    return bitmap[grid_h: grid_h + region_rows]

def extract_all(db, bitmap, width=256):
    """{(row,col): bytes} of decoded init for every BSRAM tile (data bits only)."""
    region = init_region(db, bitmap)
    if region is None:
        return {}
    out = {}
    for (r, c) in bram_tiles(db):
        parms = decode_bsram_init(db, region, r, c, width)
        out[(r, c)] = _parms_to_bytes(db, parms, width)
    return out

def _parms_to_bytes(db, parms, width):
    """Linear data-byte stream in BRAM address order (LSB-first per byte), parity excluded."""
    # replay the addr walk to order data bits; skip parity (bit_no 8,17)
    data = []
    addr = -1
    for init_row in range(0x40):
        s = parms[f'INIT_RAM_{init_row:02X}']
        bit_no = 0; ptr = -1
        while ptr >= -width:
            if bit_no == 8 or bit_no == 17:
                if width == 288:
                    ptr -= 1            # parity char consumed but not a data bit
                bit_no = (bit_no + 1) % 18
            else:
                addr += 1
                data.append(1 if s[width + ptr] == '1' else 0)
                ptr -= 1
                bit_no = (bit_no + 1) % 18
    by = bytearray((len(data) + 7) // 8)
    for i, b in enumerate(data):
        if b:
            by[i // 8] |= (1 << (i % 8))
    return bytes(by)


def _self_test(fam):
    import lzma, msgspec, importlib.resources
    from apycula import chipdb
    from apycula import gowin_pack as gp
    import apycula.bitmatrix as bm
    with importlib.resources.path('apycula', f'{fam}.msgpack.xz') as p:
        db = msgspec.msgpack.decode(lzma.open(str(p)).read(), type=chipdb.Device)
    gp.db = db
    gp.device = fam
    # a BSRAM column/row that exists (use a known scope BRAM: R10C2 = grid 9,1)
    row, col = 9, 1
    for width, subtype in ((256, ''), (288, 'X9')):
        # build a pseudo-random-but-deterministic INIT_RAM
        parms = {}
        for r in range(0x40):
            s = ''.join('1' if ((r * 131 + i * 7) % 5 == 0) else '0' for i in range(width))
            parms[f'INIT_RAM_{r:02X}'] = s
        gp.bsram_init_map = None
        gp.store_bsram_init_val(db, row, col, 'BSRAM', dict(parms), {'BSRAM_SUBTYPE': subtype})
        region = gp.bsram_init_map
        rec = decode_bsram_init(db, region, row, col, width)
        ok = all(rec[f'INIT_RAM_{r:02X}'] == parms[f'INIT_RAM_{r:02X}'] for r in range(0x40))
        nset = sum(s.count('1') for s in parms.values())
        print(f"  width={width:3} subtype={subtype or '(none)':4}: round-trip {'OK' if ok else 'FAIL'} "
              f"({nset} ones)")
        if not ok:
            for r in range(0x40):
                if rec[f'INIT_RAM_{r:02X}'] != parms[f'INIT_RAM_{r:02X}']:
                    print(f"    row {r:02X} mismatch\n     in ={parms[f'INIT_RAM_{r:02X}'][:48]}\n     out={rec[f'INIT_RAM_{r:02X}'][:48]}")
                    break
            sys.exit(1)
    print("  *** encode<->decode inverse verified for both width modes ***")

def _extract_cli(bitstream, fam, width):
    import lzma, msgspec, importlib.resources
    from apycula import chipdb
    from apycula.bslib import read_bitstream
    with importlib.resources.path('apycula', f'{fam}.msgpack.xz') as p:
        db = msgspec.msgpack.decode(lzma.open(str(p)).read(), type=chipdb.Device)
    bitmap, _, _, _ = read_bitstream(bitstream)
    res = extract_all(db, bitmap, width)
    if not res:
        print("no BRAM-init region in this bitstream (bit_incl_bsram_init was off)")
        return
    for (r, c), data in sorted(res.items()):
        nz = sum(1 for b in data if b)
        head = ' '.join(f'{b:02x}' for b in data[:16])
        print(f"BSRAM @ R{r+1}C{c+1}: {len(data)} bytes, {nz} non-zero | first16: {head}")

if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] not in ("--selftest",) and os.path.exists(a[0]):
        # extract mode: bsram_init_decode.py <bitstream> [-d FAM] [--width N]
        fam = a[a.index('-d') + 1] if '-d' in a else "GW1N-2"
        width = int(a[a.index('--width') + 1]) if '--width' in a else 256
        _extract_cli(a[0], fam, width)
    else:
        _self_test(a[1] if len(a) > 1 else "GW1N-2")
