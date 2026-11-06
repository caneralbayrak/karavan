#!/bin/sh
# Cellebrite Touch seri yuva (SOURCE/TARGET) acma - TEK KOMUT KURULUM
# Kullanim:  sudo sh kur.sh
# Yaptiklari: cihazi kontrol eder, yuvalari acar, acilista otomatik acilmasini ayarlar,
#             getty uyarisi verir, istenirse dongu testi yapar.
DIZIN=$(cd "$(dirname "$0")" && pwd)
PORT=${PORT:-/dev/port}
KOK=${KOK:-}                       # test icin sahte kok dizin (bos = gercek sistem)
DMI=${DMI:-/sys/class/dmi/id}

if [ "$(id -u)" != 0 ] && [ -z "$KOK" ]; then
  echo "Root yetkisi gerekiyor, sudo ile yeniden calistiriliyor..."
  exec sudo sh "$0" "$@"
fi

echo "=============================================="
echo " Cellebrite Touch seri yuva kurulumu"
echo "=============================================="

# 1) Cihaz kontrolu
uretici=$(cat "$DMI/sys_vendor" 2>/dev/null); model=$(cat "$DMI/product_name" 2>/dev/null)
echo "Cihaz: $uretici $model"
case "$uretici" in
  *Cellebrite*) ;;
  *) echo "HATA: Bu cihaz Cellebrite degil. Kurulum DURDURULDU (baska cihazda calistirmak tehlikeli)."; exit 1 ;;
esac
[ -e "$PORT" ] || { echo "HATA: $PORT yok (cekirdekte CONFIG_DEVPORT gerekli)."; exit 1; }

# 2) Mevcut deger
v=$(dd if="$PORT" bs=1 skip=659 count=1 2>/dev/null | od -An -tu1 | tr -d ' \n')
printf 'Mevcut 0x293 degeri: %02x\n' "$v"
if [ $(( v & ~30 )) -ne 0 ]; then
  printf 'UYARI: Beklenmeyen deger (bizde 02 idi). Devam edilsin mi? (e/h) '; read c
  [ "$c" = e ] || { echo "Iptal edildi."; exit 1; }
fi

# 3) Betigi kur ve yuvalari ac
mkdir -p "$KOK/opt"
cp "$DIZIN/cpld_seri.sh" "$KOK/opt/cpld_seri.sh" && chmod 755 "$KOK/opt/cpld_seri.sh"
PORT="$PORT" sh "$KOK/opt/cpld_seri.sh" ac

# 4) Acilista otomatik
SATIR="sh /opt/cpld_seri.sh ac"
if [ -f "$KOK/opt/bootlocal.sh" ] || [ -d "$KOK/usr/local/tce.installed" ]; then
  echo "Sistem: Tiny Core"
  grep -q "cpld_seri.sh" "$KOK/opt/bootlocal.sh" 2>/dev/null || echo "$SATIR" >> "$KOK/opt/bootlocal.sh"
  if [ -f "$KOK/opt/.filetool.lst" ] && ! grep -q '^opt' "$KOK/opt/.filetool.lst"; then echo "opt" >> "$KOK/opt/.filetool.lst"; fi
  if [ -z "$KOK" ] && command -v filetool.sh >/dev/null; then
    echo "Yedek aliniyor (filetool.sh -b)..."; filetool.sh -b && echo "Yedek tamam."
  fi
elif [ -d "$KOK/etc/runit/rc-local" ]; then
  echo "Sistem: antiX/runit"
  printf '#!/bin/sh\n%s\n' "$SATIR" > "$KOK/etc/runit/rc-local/cpld-seri.start"; chmod 755 "$KOK/etc/runit/rc-local/cpld-seri.start"
elif [ -f "$KOK/etc/rc.local" ]; then
  echo "Sistem: rc.local"
  grep -q "cpld_seri.sh" "$KOK/etc/rc.local" || sed -i "s|^exit 0|$SATIR\nexit 0|" "$KOK/etc/rc.local"
  grep -q "cpld_seri.sh" "$KOK/etc/rc.local" || echo "$SATIR" >> "$KOK/etc/rc.local"
else
  echo "UYARI: Acilis dosyasi bulunamadi. Her acilista elle: sudo $SATIR"
fi
echo "Acilista otomatik acilma ayarlandi."

# 5) getty uyarisi
if ps 2>/dev/null | grep -v grep | grep -q "getty.*ttyS"; then
  echo "UYARI: ttyS portlarindan birinde giris ekrani (getty) calisiyor, portu mesgul eder:"
  ps | grep -v grep | grep "getty.*ttyS"
  echo "  Tiny Core: /etc/inittab icindeki ttyS satirini kaldirin. antiX: sudo rm /etc/service/getty-ttyS0"
fi

# 6) Dongu testi (istege bagli)
echo
echo "Dongu testi: ag kablosunda MAVI ile BEYAZ-MAVI teli birbirine bukun, digerlerini yalitin."
printf 'Kablo takili mi? Hangi yuvada? (s = SOURCE/sol, t = TARGET/sag, bos = testi atla) '; read y
case "$y" in s|S) P=/dev/ttyS1 ;; t|T) P=/dev/ttyS0 ;; *) P= ;; esac
if [ -n "$P" ] && [ -z "$KOK" ]; then
  stty -F $P 9600 raw -echo
  dd if=$P of=/tmp/dongu_sonuc bs=1 count=20 2>/dev/null & okuyucu=$!
  sleep 1; printf 'MERHABA-DONGU-TESTI' > $P; sleep 2; kill $okuyucu 2>/dev/null
  if grep -q MERHABA /tmp/dongu_sonuc 2>/dev/null; then
    echo ">>> BASARILI: $P yuvasi calisiyor. Gelen: $(cat /tmp/dongu_sonuc)"
  else
    echo ">>> VERI GELMEDI. Kabloyu, yuvayi ve getty uyarisini kontrol edin."
  fi
fi
echo
echo "Bitti. Durum icin:  sudo sh /opt/cpld_seri.sh durum"
echo "Kapatmak icin:      sudo sh /opt/cpld_seri.sh kapa"
