#!/usr/bin/env python3
"""Generic MCHBAR qword peek/poke. usage: genpoke.py <off_hex> [val_hex]"""
import mmap, struct, sys
BASE=0xFED10000
off=int(sys.argv[1],16)
page=(BASE+off)&~0xFFF; o=(BASE+off)-page
f=open("/dev/mem","r+b",0)
m=mmap.mmap(f.fileno(),0x1000,offset=page)
cur=struct.unpack("<Q",m[o:o+8])[0]
print("+0x%04X cur = 0x%016X (PL1=%.2fW en=%d)"%(off,cur,(cur&0x7FFF)/256.0,(cur>>15)&1))
if len(sys.argv)>2:
    nv=int(sys.argv[2],16)
    m[o:o+8]=struct.pack("<Q",nv)
    rb=struct.unpack("<Q",m[o:o+8])[0]
    print("  wrote 0x%016X -> rb 0x%016X %s (PL1=%.2fW)"%(nv,rb,"OK" if rb==nv else "FAIL",(rb&0x7FFF)/256.0))
m.close(); f.close()
