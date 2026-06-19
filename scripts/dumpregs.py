#!/usr/bin/env python3
import mmap, struct
BASE=0xFED10000
f=open("/dev/mem","r+b",0)
m=mmap.mmap(f.fileno(),0x8000,offset=BASE)
# dump 0x7080..0x7100 as qwords, decode any that look like RAPL limits
for off in range(0x7080,0x7100,8):
    q=struct.unpack("<Q",m[off:off+8])[0]
    note=""
    lim=q&0x7FFF; en=(q>>15)&1
    if en and 0 < lim < 0x4000:
        note=" <- limit? L=%.2fW en=%d (lo15)"%(lim/256.0,en)
    print("+0x%04X = 0x%016X%s"%(off,q,note))
print("--- also scan whole window for ANY enabled-limit qword 4W..16W ---")
for off in range(0,0x8000,4):
    q=struct.unpack("<Q",m[off:off+8])[0]
    lim=q&0x7FFF; en=(q>>15)&1
    if en and 0x400<=lim<=0x1000 and (q>>16)&0xFF in (0xdd,0x00,0x80,0xde):
        print("  +0x%04X = 0x%016X  L=%.2fW"%(off,q,lim/256.0))
m.close(); f.close()
