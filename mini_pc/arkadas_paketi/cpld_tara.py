#!/usr/bin/env python3
# CPLD (IO 0x290-0x29F) belgesiz yazmaclarinda bit bit deneme + seri dongu testi.
# Her bit degistirilir, test edilir, HEMEN eski degerine dondurulur.
import os, sys, time, signal, termios, fcntl, struct, select

BASE = 0x290
ADAYLAR = [0x293, 0x294, 0x295, 0x296, 0x297, 0x299, 0x29A, 0x29C, 0x29D]
LOG = '/home/karavan/cpld_tarama.log'
PORTLAR = ['/dev/ttyS0', '/dev/ttyS1']

logf = open(LOG, 'w', buffering=1)
def log(s):
    logf.write(time.strftime('%H:%M:%S ') + s + '\n')

pfd = os.open('/dev/port', os.O_RDWR)
def inb(a): return os.pread(pfd, 1, a)[0]
def outb(a, v): os.pwrite(pfd, bytes([v & 0xFF]), a)
def kilit_ac(): outb(0x29E, 0x5A); outb(0x29F, 0xA5)
def kilitle():  outb(0x29E, 0x00); outb(0x29F, 0x00)
def dokum(): return ' '.join('%02x' % inb(BASE + i) for i in range(16))

ORIJINAL = {a: inb(a) for a in ADAYLAR}

def geri_yukle():
    kilit_ac()
    for a, v in ORIJINAL.items():
        outb(a, v)
    kilitle()

def cikis(*_):
    geri_yukle()
    log('SINYAL/CIKIS: orijinal degerler geri yuklendi: ' + dokum())
    sys.exit(0)
for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
    signal.signal(s, cikis)

TIOCM = {'DTR': 0x002, 'RTS': 0x004, 'CTS': 0x020, 'DCD': 0x040, 'RI': 0x080, 'DSR': 0x100}
def ac(port):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    a = termios.tcgetattr(fd)
    a[0] = 0; a[1] = 0; a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL; a[3] = 0
    a[4] = a[5] = termios.B9600
    termios.tcsetattr(fd, termios.TCSANOW, a)
    fcntl.ioctl(fd, termios.TIOCMBIS, struct.pack('I', TIOCM['DTR'] | TIOCM['RTS']))
    return fd
def modem(fd):
    v = struct.unpack('I', fcntl.ioctl(fd, termios.TIOCMGET, struct.pack('I', 0)))[0]
    return ''.join(k[0] for k in ('CTS', 'DCD', 'DSR', 'RI') if v & TIOCM[k]) or '-'
def dongu(fd):
    termios.tcflush(fd, termios.TCIOFLUSH)
    msg = b'DONGU-0123456789'
    os.write(fd, msg); termios.tcdrain(fd)
    got = b''; t = time.time()
    while time.time() - t < 0.25:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r: got += os.read(fd, 256)
    return msg in got, len(got), modem(fd)

fds = {p: ac(p) for p in PORTLAR}
def test():
    out = []
    for p, fd in fds.items():
        ok, n, m = dongu(fd)
        out.append('%s:%s gelen=%d modem=%s' % (os.path.basename(p), 'DONGU-VAR!!!' if ok else 'yok', n, m))
    return ' | '.join(out)

try:
    log('BASLANGIC dokum: ' + dokum())
    log('TEMEL test: ' + test())
    for a in ADAYLAR:
        for bit in range(8):
            yeni = ORIJINAL[a] ^ (1 << bit)
            kilit_ac(); outb(a, yeni); geri = inb(a); kilitle()
            time.sleep(0.3)
            sonuc = test()
            kilit_ac(); outb(a, ORIJINAL[a]); kilitle()
            time.sleep(0.1)
            yaz = 'yazildi' if geri == yeni else 'TUTMADI(okunan %02x)' % geri
            log('0x%03X bit%d %02x->%02x %s | %s' % (a, bit, ORIJINAL[a], yeni, yaz, sonuc))
    log('BITIS dokum: ' + dokum())
finally:
    geri_yukle()
    log('SON: orijinal degerler geri yuklendi: ' + dokum())
    log('TAMAMLANDI')
