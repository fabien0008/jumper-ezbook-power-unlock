#!/usr/bin/env python3
"""Correct AMI NVAR Setup variable tool for Jumper EZbook.
Flag bits: 0x80=VALID 0x40=AUTH 0x20=HWERR 0x10=EXT 0x08=DATA_ONLY 0x04=GUID 0x02=ASCII 0x01=RT"""
import os, struct, sys, fcntl, ctypes

MTD='/dev/mtd0'; ESZ=0x1000; MEMERASE=0x40084d02
STORE_HEADS=[0x1D55C1, 0x1F55C1]   # Setup NVAR head in each store

class ei(ctypes.Structure): _fields_=[("start",ctypes.c_uint32),("length",ctypes.c_uint32)]

def data_start(buf, pos):
    """Return offset where this NVAR's data begins (relative to file)."""
    flags=buf[pos+9]
    if flags & 0x08:            # DATA_ONLY -> header is 10 bytes
        return pos+10
    p=pos+10
    p += 16 if (flags & 0x04) else 1     # inline GUID or 1-byte index
    if flags & 0x02:                      # ASCII name, null-terminated
        p = buf.index(b'\x00', p)+1
    return p

def chain_entries(buf, head):
    """Yield (pos, data_start) for head and every chained copy; last is current."""
    pos=head
    while True:
        if buf[pos:pos+4]!=b'NVAR': return
        ds=data_start(buf,pos)
        nxt=struct.unpack('<I', buf[pos+6:pos+9]+b'\x00')[0]
        yield pos, ds, (nxt==0xFFFFFF or nxt==0)
        if nxt==0xFFFFFF or nxt==0: return
        pos+=nxt

def show():
    buf=open(MTD,'rb').read(0x200000)
    fields=[(0x3AF,"DVMT pre-alloc",{2:"64M",3:"96M",4:"128M",8:"256M",16:"512M"}),
            (0x3B0,"DVMT total",{1:"128M",2:"256M",3:"MAX"}),
            (0x10D,"Aperture",{0:"128M",1:"256M",2:"512M",3:"1024M"}),
            (0x3B1,"GOP Driver",{0:"VBIOS",1:"GOP"}),
            (0x3B2,"GOP Brightness",None),
            (0x56,"Max Core C-state",{0:"C0",6:"C6",7:"C7",8:"C10"}),
            (0x57,"C-state auto-demote",{0:"Off",1:"On"}),
            (0x58,"C-state un-demote",{0:"Off",1:"On"})]
    for si,head in enumerate(STORE_HEADS):
        ents=list(chain_entries(buf,head))
        if not ents: 
            print(f"Store{si}: no entries"); continue
        cur_pos,cur_ds,_=ents[-1]
        print(f"\nStore{si} head=0x{head:06X} chainlen={len(ents)} current=0x{cur_pos:06X} (data+{cur_ds-cur_pos})")
        for off,nm,m in fields:
            v=buf[cur_ds+off]
            disp = m.get(v,f"0x{v:02X}") if m else str(v)
            print(f"   [0x{off:03X}] {nm:<20s}=0x{v:02X} {disp}")

def write_bytes(changes):
    """changes: list of (var_offset, value). Applies to CURRENT entry of every store."""
    fd=os.open(MTD, os.O_RDWR|os.O_SYNC)
    buf=os.pread(fd,0x200000,0)
    targets=[]
    for head in STORE_HEADS:
        ents=list(chain_entries(buf,head))
        if ents:
            _,cur_ds,_=ents[-1]
            targets.append(cur_ds)
    for ds in targets:
        for off,val in changes:
            fa=ds+off
            sec=(fa//ESZ)*ESZ; bo=fa-sec
            sd=bytearray(os.pread(fd,ESZ,sec))
            if sd[bo]==val: 
                print(f"  @0x{fa:06X}(off0x{off:03X}) already 0x{val:02X}"); continue
            old=sd[bo]; sd[bo]=val
            fcntl.ioctl(fd, MEMERASE, ei(sec,ESZ))
            os.pwrite(fd, bytes(sd), sec)
            chk=os.pread(fd,1,fa)[0]
            print(f"  @0x{fa:06X}(off0x{off:03X}) 0x{old:02X}->0x{val:02X} {'OK' if chk==val else 'FAIL'}")
    os.close(fd)

if __name__=='__main__':
    cmd=sys.argv[1] if len(sys.argv)>1 else 'show'
    if cmd=='show': show()
    elif cmd=='restore':
        # pristine defaults for every byte my off-by-2 bug + v2 touched
        write_bytes([(0x10D,0x01),(0x10F,0x00),(0x3AF,0x02),(0x3B0,0x02),
                     (0x3B1,0x01),(0x3B2,0x08),(0x56,0x08),(0x57,0x01),
                     (0x58,0x01),(0x59,0x00),(0x5A,0x00)])
        print("Restored to pristine defaults.")
