#!/bin/sh
# Cellebrite Touch (UFED Touch NB13): SOURCE/TARGET RJ45 seri yuvalarini ac/kapa.
# CPLD yazmaci IO 0x293:  bit2=1,bit1=0 -> ttyS1 SOURCE (sol)  |  bit4=1,bit3=0 -> ttyS0 TARGET (sag)
# Kilit: 0x29E=0x5A, 0x29F=0xA5 yaz -> degistir -> ikisine 0x00 yaz.
# Kullanim (root):  cpld_seri.sh ac | kapa | durum
PORT=${PORT:-/dev/port}
ADR=659     # 0x293
LOK1=670    # 0x29E
LOK2=671    # 0x29F
oku()  { dd if="$PORT" bs=1 skip="$1" count=1 2>/dev/null | od -An -tu1 | tr -d ' \n'; }
yaz()  { printf "\\$(printf '%03o' "$2")" | dd of="$PORT" bs=1 seek="$1" count=1 conv=notrunc 2>/dev/null; }
v=$(oku $ADR)
case "${1:-durum}" in
  ac)   yeni=$(( (v & ~30) | 20 )) ;;   # 30=0x1E, 20=0x14
  kapa) yeni=$(( (v & ~30) | 2 ))  ;;   # fabrika degeri 0x02
  durum) yeni= ;;
  *) echo "kullanim: $0 ac|kapa|durum"; exit 1 ;;
esac
if [ -n "$yeni" ]; then
  yaz $LOK1 90; yaz $LOK2 165      # kilit ac (0x5A, 0xA5)
  yaz $ADR $yeni
  yaz $LOK1 0;  yaz $LOK2 0        # kilitle
  v=$(oku $ADR)
fi
src=KAPALI; [ $(( v & 6 )) -eq 4 ] && src=ACIK
tgt=KAPALI; [ $(( v & 24 )) -eq 16 ] && tgt=ACIK
printf '0x293 = %02x   ttyS1->SOURCE: %s   ttyS0->TARGET: %s\n' "$v" "$src" "$tgt"
