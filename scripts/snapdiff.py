#!/usr/bin/env python3
"""Snapshot MCHBAR RAPL region idle vs GPU-active and diff.
Energy/status counters change constantly; we flag those and highlight the rest."""
import mmap, struct, subprocess, time, os, signal

BASE=0xFED10000; LO=0x7000; HI=0x8000
# offsets known to be free-running counters (energy/status) -> ignore
COUNTERS={0x70C0,0x70C8,0x70D0,0x70D8,0x70E0,0x70E8}

f=open("/dev/mem","r+b",0)
m=mmap.mmap(f.fileno(),0x8000,offset=BASE)

def snap():
    return {off:struct.unpack("<Q",m[off:off+8])[0] for off in range(LO,HI,8)}

a=snap()
# start GPU load
env=dict(os.environ, DISPLAY=":0"); env["vblank_mode"]="0"
p=subprocess.Popen(["glxgears","-fullscreen"],env=env,
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(4)
b=snap()
p.send_signal(signal.SIGTERM);
time.sleep(0.3)
try: p.kill()
except: pass

print("changed MCHBAR qwords (idle -> GPU active), excluding known counters:")
any_=False
for off in range(LO,HI,8):
    if a[off]!=b[off]:
        tag=" [counter]" if off in COUNTERS else ""
        print("  +0x%04X: 0x%016X -> 0x%016X%s"%(off,a[off],b[off],tag))
        if off not in COUNTERS: any_=True
if not any_: print("  (only counters changed)")
m.close(); f.close()
