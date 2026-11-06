#!/usr/bin/env python3
# Cellebrite Touch CPLD seri yuva yonlendirmesi (IO 0x293), 2026-11-06 deneyle bulundu:
#   bit2=1 bit1=0 -> ttyS1 SOURCE (sol) RJ45 ;  bit4=1 bit3=0 -> ttyS0 TARGET (sag) RJ45
#   RJ45 pin 4-5 (mavi / beyaz-mavi) = TX/RX ciftı (dongu testi ile)
# Kullanim: sudo cpld_seri ac | kapa | durum      (kapa = fabrika degeri 0x02)
import os, sys
ADR = 0x293
fd = os.open('/dev/port', os.O_RDWR)
inb = lambda a: os.pread(fd, 1, a)[0]
def outb(a, v): os.pwrite(fd, bytes([v & 0xFF]), a)
komut = sys.argv[1] if len(sys.argv) > 1 else 'durum'
v = inb(ADR)
if komut in ('ac', 'kapa'):
    yeni = ((v & ~0x1E) | 0x14) if komut == 'ac' else ((v & ~0x1E) | 0x02)
    outb(0x29E, 0x5A); outb(0x29F, 0xA5)   # kilit ac
    outb(ADR, yeni)
    outb(0x29E, 0x00); outb(0x29F, 0x00)   # kilitle
    v = inb(ADR)
src = (v & 0x06) == 0x04
tgt = (v & 0x18) == 0x10
print('0x293 = %02x  ttyS1->SOURCE: %s  ttyS0->TARGET: %s' % (v, 'ACIK' if src else 'KAPALI', 'ACIK' if tgt else 'KAPALI'))
