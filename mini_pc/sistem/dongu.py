import os, sys, termios, fcntl, struct, time, select
port = sys.argv[1]
def irq(n):
    for l in open('/proc/interrupts'):
        if n in l: return int(l.split()[1])
    return None
TIOCM = {'DTR':0x002,'RTS':0x004,'CTS':0x020,'DCD':0x040,'RI':0x080,'DSR':0x100}
def modem(fd):
    v = struct.unpack('I', fcntl.ioctl(fd, termios.TIOCMGET, struct.pack('I',0)))[0]
    return ' '.join(k for k,b in TIOCM.items() if v & b) or '-'
def setm(fd, on):
    bits = struct.pack('I', TIOCM['DTR']|TIOCM['RTS'])
    fcntl.ioctl(fd, termios.TIOCMBIS if on else termios.TIOCMBIC, bits)
fd = os.open(port, os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
a = termios.tcgetattr(fd)
a[0]=0; a[1]=0; a[2]=termios.CS8|termios.CREAD|termios.CLOCAL; a[3]=0
a[4]=a[5]=termios.B9600
termios.tcsetattr(fd, termios.TCSANOW, a)
n = os.path.basename(port)
for on in (False, True):
    setm(fd, on); time.sleep(0.3)
    termios.tcflush(fd, termios.TCIOFLUSH)
    i0 = irq(n)
    msg = b'DONGU-TESTI-0123456789-UUUU'
    os.write(fd, msg); termios.tcdrain(fd)
    got = b''; t = time.time()
    while time.time()-t < 1.0:
        r,_,_ = select.select([fd],[],[],0.1)
        if r: got += os.read(fd, 256)
    print(f"{n} DTR/RTS {'ACIK ' if on else 'KAPALI'} | modem: {modem(fd):20s} | kesme +{irq(n)-i0} | gonderilen {len(msg)} bayt, gelen {len(got)}: {got[:40]!r} {'-> DONGU CALISIYOR' if msg in got else ''}")
os.close(fd)
