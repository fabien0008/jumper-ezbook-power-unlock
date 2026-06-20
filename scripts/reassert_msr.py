#!/usr/bin/env python3
"""Continuously re-assert MSR 0x610 (PKG_POWER_LIMIT) to <val> on all CPUs until
the flag file disappears. Used for the >10W ladder where the MSR is NOT locked,
so PCODE would otherwise reset it to 6W on GPU activity.
Usage: reassert_msr.py <hexval> <flagfile>
"""
import os, struct, sys, glob, time

val = int(sys.argv[1], 16)
flag = sys.argv[2]
paths = sorted(glob.glob("/dev/cpu/*/msr"))
while os.path.exists(flag):
    for p in paths:
        try:
            fd = os.open(p, os.O_WRONLY)
            os.pwrite(fd, struct.pack("<Q", val), 0x610)
            os.close(fd)
        except OSError:
            pass
    time.sleep(0.8)
