#!/usr/bin/env python3
"""Read/write MMIO PACKAGE_RAPL_LIMIT in MCHBAR on Apollo Lake.
MCHBAR base from PCI 0:0.0 off 0x48 = 0xFED10000; PKG RAPL LIMIT at +0x59A0.
Usage: mmio_rapl.py            -> show
       mmio_rapl.py <newval>   -> write 64-bit hex value
"""
import mmap, struct, sys

BASE = 0xFED10000
OFF = 0x70A8   # Apollo Lake PACKAGE_RAPL_LIMIT MMIO mirror (NOT Core 0x59A0)

def decode(val):
    pl1 = val & 0x7FFF; pl1en = (val >> 15) & 1; clamp1 = (val >> 16) & 1
    pl2 = (val >> 32) & 0x7FFF; pl2en = (val >> 47) & 1
    lock = (val >> 63) & 1
    print("  PL1 = %.2f W (raw 0x%X) en=%d clamp=%d" % (pl1/256.0, pl1, pl1en, clamp1))
    print("  PL2 = %.2f W (raw 0x%X) en=%d" % (pl2/256.0, pl2, pl2en))
    print("  LOCK bit63 =", lock)

def main():
    pa = BASE + OFF
    page = pa & ~0xFFF
    o = pa - page
    f = open("/dev/mem", "r+b", 0)
    m = mmap.mmap(f.fileno(), 0x1000, offset=page)
    val = struct.unpack("<Q", m[o:o+8])[0]
    print("MMIO PKG_RAPL_LIMIT @0x%X = 0x%016X" % (pa, val))
    decode(val)
    if len(sys.argv) > 1:
        newval = int(sys.argv[1], 16)
        if (val >> 63) & 1:
            print("LOCKED - write will not stick");
        m[o:o+8] = struct.pack("<Q", newval)
        rb = struct.unpack("<Q", m[o:o+8])[0]
        print("WROTE 0x%016X -> readback 0x%016X %s" % (newval, rb, "OK" if rb == newval else "FAIL"))
        decode(rb)
    m.close(); f.close()

main()
