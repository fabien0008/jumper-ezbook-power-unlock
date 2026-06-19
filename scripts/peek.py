#!/usr/bin/env python3
import nvar
buf = open(nvar.MTD, 'rb').read(0x200000)
offs = [(0x4D,"EIST"),(0x5B,"Turbo Mode"),(0xE9,"TDC Limit (A) lo"),(0xEA,"TDC hi"),
        (0xEC,"TDP Limit (W) lo"),(0xED,"TDP hi")]
for si, head in enumerate(nvar.STORE_HEADS):
    ents = list(nvar.chain_entries(buf, head))
    if not ents:
        print(f"Store{si}: none"); continue
    _, ds, _ = ents[-1]
    print(f"Store{si} current data+{ds:#x}")
    for off, nm in offs:
        print(f"   [0x{off:03X}] {nm:<18s} = 0x{buf[ds+off]:02X} ({buf[ds+off]})")
