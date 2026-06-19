#!/usr/bin/env python3
"""Raise Jumper EZbook (Celeron N3450, Apollo Lake) package power limit PL1 to 10W
in ALL workloads (CPU-only AND GPU/mixed).

The PUnit enforces min(MMIO RAPL limit, MSR RAPL limit). The FSP sets BOTH to the
fused 6W TDP. Two writes are needed, and the MSR must be LOCKED:

  1. MMIO PACKAGE_RAPL_LIMIT  @ MCHBAR(0xFED10000)+0x70A8  := PL1 10W / PL2 15W
  2. MSR  PKG_POWER_LIMIT (0x610)                          := PL1 10W / PL2 15W + LOCK(bit63)

Why the lock: PCODE resets the *MSR* copy back to 6W whenever the iGPU goes active
(the "GPU latch"); min(10W, 6W) = 6W. Setting bit63 locks the MSR so PCODE cannot
reset it, and min(10W, 10W) = 10W holds with the GPU busy too.

All volatile (lost on reboot) -> run at every boot via systemd.
"""
import mmap, struct, sys, glob, os

MCHBAR = 0xFED10000
MMIO_OFF = 0x70A8
MMIO_VAL = 0x00008F0000DD8A00        # PL1=10W clamp+en, PL2=15W en, ~28s window
MSR_PKG_POWER_LIMIT = 0x610
MSR_VAL = 0x80008F0000DD8A00         # same + bit63 LOCK

def write_mmio():
    pa = MCHBAR + MMIO_OFF
    page = pa & ~0xFFF; o = pa - page
    with open("/dev/mem", "r+b", 0) as f:
        m = mmap.mmap(f.fileno(), 0x1000, offset=page)
        if (struct.unpack("<Q", m[o:o+8])[0] >> 63) & 1:
            print("MMIO RAPL limit locked; skipping", file=sys.stderr)
        else:
            m[o:o+8] = struct.pack("<Q", MMIO_VAL)
        rb = struct.unpack("<Q", m[o:o+8])[0]
        m.close()
    print("MMIO 0x%04X = 0x%016X (PL1=%.0fW) %s" % (
        MMIO_OFF, rb, (rb & 0x7FFF)/256.0, "OK" if rb == MMIO_VAL else "DIFF"))

def write_msr():
    paths = sorted(glob.glob("/dev/cpu/*/msr"))
    if not paths:
        os.system("modprobe msr 2>/dev/null")
        paths = sorted(glob.glob("/dev/cpu/*/msr"))
    ok = 0
    for p in paths:
        try:
            fd = os.open(p, os.O_RDWR)
            os.pwrite(fd, struct.pack("<Q", MSR_VAL), MSR_PKG_POWER_LIMIT)
            rb = struct.unpack("<Q", os.pread(fd, 8, MSR_PKG_POWER_LIMIT))[0]
            os.close(fd)
            if rb == MSR_VAL:
                ok += 1
        except OSError as e:
            print("  %s: %s" % (p, e), file=sys.stderr)
    print("MSR 0x610 = 0x%016X (PL1=10W+lock) on %d/%d CPUs" % (MSR_VAL, ok, len(paths)))

if __name__ == "__main__":
    write_mmio()
    write_msr()
