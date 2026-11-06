#!/bin/sh
# Cellebrite Touch: on yuzdeki L ve R tuslarini acar.
# L/R tuslari dahili bir PS/2 farenin sol/sag tusudur. Cekirdek i8042 denetleyicisini
# "aktif MUX" kipinde calistirdigi icin bu fare bulunamaz. Acilis satirina i8042.nomux=1
# eklenince "PS/2 Generic Mouse" olarak gorunur.
# Kullanim:  sudo sh tuslar.sh      (1. calistirma: ayari ekler; yeniden baslat; 2. calistirma: kontrol)
KOK=${KOK:-}                       # test icin sahte kok (bos = gercek sistem)
CMDLINE=${CMDLINE:-/proc/cmdline}
PARAM="i8042.nomux=1"

if [ "$(id -u)" != 0 ] && [ -z "$KOK" ]; then exec sudo sh "$0" "$@"; fi
echo "=============================================="
echo " Cellebrite Touch - L / R tuslari"
echo "=============================================="

# --- Zaten etkin mi? ---
if grep -q "$PARAM" "$CMDLINE" 2>/dev/null; then
  echo "Acilis ayari ETKIN ($PARAM)."
  if grep -q "PS/2 Generic Mouse\|PS/2.*Mouse" "$KOK/proc/bus/input/devices" 2>/dev/null || grep -q "PS/2.*Mouse" /proc/bus/input/devices 2>/dev/null; then
    echo ">>> BASARILI: dahili PS/2 fare bulundu. L = sol tik (button 1), R = sag tik (button 3)."
    echo
    echo "Not: L/R, imlecin son dokunulan yerinde tiklama yapar. Tiklamasin, programlar ayri yakalasin"
    echo "isterseniz grafik oturum acilisina su satiri ekleyin (Tiny Core: ~/.X.d/ icine bir dosya):"
    echo '    xinput set-button-map "PS/2 Generic Mouse" 8 2 9'
    echo "Boylece L = tus 8, R = tus 9 olur."
  else
    echo ">>> Ayar etkin ama PS/2 fare gorunmuyor. 'cat /proc/bus/input/devices' ciktisini gonderin."
  fi
  exit 0
fi

# --- Acilis yoneticisi dosyalarini bul ---
echo "Acilis ayari henuz yok. Acilis yoneticisi dosyalari araniyor..."
ADAY=""
# Debian/antiX tarzi GRUB
[ -f "$KOK/etc/default/grub" ] && ADAY="$ADAY $KOK/etc/default/grub"
# Tiny Core: acilis bolumu cogu zaman /mnt/sdXN altinda ve bagli degil -> bagla
if [ -z "$KOK" ] && [ -d /mnt ]; then
  for m in /mnt/*; do
    [ -d "$m" ] || continue
    grep -q " $m " /proc/mounts || mount "$m" 2>/dev/null
  done
fi
for f in "$KOK"/mnt/*/boot/extlinux/extlinux.conf "$KOK"/mnt/*/boot/syslinux/syslinux.cfg \
         "$KOK"/mnt/*/boot/grub/menu.lst "$KOK"/mnt/*/boot/grub/grub.cfg \
         "$KOK"/boot/extlinux/extlinux.conf "$KOK"/boot/grub/menu.lst; do
  [ -f "$f" ] && ADAY="$ADAY $f"
done
# /etc/default/grub varsa grub.cfg'yi elle degistirme (update-grub uretir)
if echo "$ADAY" | grep -q "/etc/default/grub"; then
  ADAY=$(for f in $ADAY; do case "$f" in */grub/grub.cfg) ;; *) echo "$f" ;; esac; done)
fi
ADAY=$(echo $ADAY)
if [ -z "$ADAY" ]; then
  echo "HATA: Acilis yoneticisi dosyasi bulunamadi."
  echo "Elle ekleyin: acilis satirinin (APPEND / kernel / linux) sonuna  $PARAM"
  exit 1
fi
echo "Degistirilecek dosya(lar):"; for f in $ADAY; do echo "   $f"; done
printf "Her birinin .yedek kopyasi alinip acilis satirina %s eklensin mi? (e/h) " "$PARAM"; read c
[ "$c" = e ] || { echo "Iptal edildi, hicbir sey degismedi."; exit 1; }

for f in $ADAY; do
  [ -f "$f.yedek" ] || cp "$f" "$f.yedek" || { echo "HATA: $f yedeklenemedi"; exit 1; }
  case "$f" in
    */etc/default/grub)
      sed -i "/^GRUB_CMDLINE_LINUX_DEFAULT=/{/$PARAM/!s/\"\$/ $PARAM\"/}" "$f"
      grep "^GRUB_CMDLINE_LINUX_DEFAULT=" "$f"
      if [ -z "$KOK" ]; then
        if command -v update-grub >/dev/null; then update-grub
        elif command -v grub-mkconfig >/dev/null; then grub-mkconfig -o /boot/grub/grub.cfg
        else echo "UYARI: update-grub bulunamadi, grub.cfg'yi kendiniz guncelleyin."; fi
      fi ;;
    */extlinux.conf|*/syslinux.cfg)
      sed -i "/^[[:space:]]*[Aa][Pp][Pp][Ee][Nn][Dd][[:space:]]/{/$PARAM/!s/\$/ $PARAM/}" "$f"
      grep -i "^[[:space:]]*append" "$f" ;;
    */menu.lst)
      sed -i "/^[[:space:]]*kernel[[:space:]]/{/$PARAM/!s/\$/ $PARAM/}" "$f"
      grep "^[[:space:]]*kernel" "$f" ;;
    */grub.cfg)
      sed -i "/^[[:space:]]*linux[[:space:]].*vmlinuz/{/$PARAM/!s/\$/ $PARAM/}" "$f"
      grep "^[[:space:]]*linux[[:space:]]" "$f" ;;
  esac
done
echo
echo ">>> Ayar eklendi. Cihazi YENIDEN BASLATIN, sonra kontrol icin tekrar:  sudo sh tuslar.sh"
echo "    Geri almak icin .yedek dosyalarini eski adlarina kopyalayin."
