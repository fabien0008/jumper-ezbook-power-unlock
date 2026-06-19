#!/usr/bin/env python3
"""Scan MCHBAR for liveness + RAPL-limit signature."""
import mmap, struct

BASE = 0xFED10000
SIZE = 0x8000  # 32KB MCHBAR window

f = open("/dev/mem", "r+b", 0)
m = mmap.mmap(f.fileno(), SIZE, offset=BASE)
data = m[:]

# 1) liveness: count nonzero dwords, show first few nonzero offsets
nz = []
for off in range(0, SIZE, 4):
    v = struct.unpack("<I", data[off:off+4])[0]
    if v != 0:
        nz.append((off, v))
print("nonzero dwords: %d / %d" % (len(nz), SIZE//4))
print("first nonzero offsets:")
for off, v in nz[:12]:
    print("   +0x%04X = 0x%08X" % (off, v))

# 2) RAPL signature hunt: look for PL2 word 0x8f00 and the dd86 pattern
print("\n-- scanning for RAPL-like patterns --")
for off in range(0, SIZE-8, 4):
    q = struct.unpack("<Q", data[off:off+8])[0]
    pl1 = q & 0x7FFF; pl2 = (q >> 32) & 0x7FFF
    en1 = (q >> 15) & 1; en2 = (q >> 47) & 1
    # factory: PL1=0x600(6W) or 0xA00(10W), PL2=0xF00(15W), both enabled
    if en1 and en2 and pl2 in (0xF00, 0x780) and 0x300 <= pl1 <= 0xC00:
        print("   +0x%04X = 0x%016X  PL1=%.2fW PL2=%.2fW" % (off, q, pl1/256, pl2/256))

# also raw byte search for 0x8f00 word anywhere
print("\n-- raw 0x8f00 word occurrences (LE bytes 00 8f) --")
idx = 0
hits = 0
while True:
    i = data.find(b'\x00\x8f', idx)
    if i < 0 or hits > 30: break
    print("   @+0x%04X" % i); idx = i+1; hits += 1

m.close(); f.close()
