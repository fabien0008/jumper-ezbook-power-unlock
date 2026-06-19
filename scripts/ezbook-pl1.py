#!/usr/bin/env python3
"""Raise Jumper EZbook (Celeron N3450, Apollo Lake) package power limit PL1 to 10W.

Writes the MMIO PACKAGE_RAPL_LIMIT register at MCHBAR(0xFED10000)+0x70A8.
This is the ONLY lever that works on this locked SKU (MSR 0x610 is ignored by
PCODE; the BIOS "TDP Limit" NVAR is not plumbed). Volatile -> run at every boot.

NOTE: only benefits CPU-bound work with the iGPU idle. Any GPU activity makes
the PUNIT latch the package back to ~6W regardless of this register.
"""
import mmap, struct, sys

MCHBAR = 0xFED10000
OFF = 0x70A8
# PL1=10W(0xA00) clamp+en, PL2=15W(0xF00) en, ~28s window -> 0x00008f0000dd8a00
TARGET = 0x00008F0000DD8A00

def main():
    pa = MCHBAR + OFF
    page = pa & ~0xFFF
    o = pa - page
    f = open("/dev/mem", "r+b", 0)
    m = mmap.mmap(f.fileno(), 0x1000, offset=page)
    cur = struct.unpack("<Q", m[o:o+8])[0]
    if (cur >> 63) & 1:
        print("RAPL limit is locked (bit63); cannot write", file=sys.stderr)
        return 1
    m[o:o+8] = struct.pack("<Q", TARGET)
    rb = struct.unpack("<Q", m[o:o+8])[0]
    m.close(); f.close()
    ok = rb == TARGET
    print("PL1 set to %.0fW (0x%016X) %s" % ((TARGET & 0x7FFF)/256.0, rb,
          "OK" if ok else "FAIL"))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
