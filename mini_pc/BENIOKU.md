# Mini PC (192.168.1.117, antiX 26.1 32-bit, kullanıcı `karavan`) kiosk dosyaları

Masaüstü yok. Açılış: tty1 otomatik giriş → `~/.bash_profile` → `startx` → `~/.xinitrc`
→ PipeWire + `~/karavan/kiosk.sh` → panel. Panel kapanırsa kiosk.sh 3 sn sonra yeniden açar,
ekran oturumu kapanırsa .bash_profile 3 sn sonra yeniden başlatır.

| Dosya burada | Mini PC'deki yeri |
|---|---|
| kiosk.sh | ~/karavan/kiosk.sh |
| kiosk-yeniden.sh | ~/karavan/kiosk-yeniden.sh (paneli yeniden açar; kiosk.sh'i öldürmeyin) |
| xinitrc | ~/.xinitrc |
| bash_profile | ~/.bash_profile |
| firefox-user.js | ~/.karavan-kiosk/user.js (Firefox seçilirse) |

Panel seçimi: `~/karavan/tarayici` dosyası → `yerel` (Python/Tk, ../yerel_panel/panel.py) ya da `firefox`.
Yerel panel ve web paneli (../panel) mini PC'ye scp ile kopyalanır.

Sudo ile yapılmış sistem ayarları:
- /etc/sv/getty-tty1/run: `getty --autologin karavan --noclear 38400 tty1 linux`
- Kapatılan servisler (/etc/service linkleri silindi): slimski, cups, saned, gpm, rsync
  (masaüstüne dönmek: `sudo ln -s /etc/sv/slimski /etc/service/`)
- /etc/acpi/events/{battery,ac} → *.kapali (pil olayları CPU'yu %50 meşgul ediyordu), tlp kaldırıldı
- connman saat eşitleme: TimeUpdates=auto, tr.pool.ntp.org
- Paketler: python3-tk python3-paho-mqtt (yerel panel), chromium/surf (denendi, kullanılmıyor)
