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

## Donanım: Cellebrite Touch (UFED Touch, NB13, BIOS 6.04, Intel US15W, Atom Z510)

### Seri yuvalar (2026-11-06)
Ön taraftaki **SOURCE** (sol) ve **TARGET** (sağ) RJ45 yuvaları seri port. Cellebrite'ın CPLD yongası
(I/O 0x290–0x29F) bağlıyor; Linux'ta kendiliğinden kapalı. Anahtar **0x293** yazmacı:

| Bitler | Sonuç |
|---|---|
| bit2=1, bit1=0 | ttyS1 → SOURCE |
| bit4=1, bit3=0 | ttyS0 → TARGET |

Fabrika `0x02`, ikisi açık `0x14`. Yazmadan önce kilit: 0x29E←0x5A, 0x29F←0xA5, sonra ikisine 0x00.

| Ağ kablosu teli (T568B) | Pin | Görev |
|---|---|---|
| beyaz-mavi | 5 | TX (mini PC gönderir) |
| mavi | 4 | RX (mini PC alır) |
| beyaz-yeşil + kahverengi | 3 + 8 | GND (instructables kaynağına göre; **süreklilik testiyle doğrulanmadı**) |

Sinyal **3.3 V TTL** (boşta ~2.5 V ölçüldü, RS-232 DEĞİL). RS-232 cihaz → araya MAX3232 (3.3 V).
Döngü testi: mavi + beyaz-mavi bükülü → `python3 ~/dongu.py /dev/ttyS0`.

### Sudo ile yapılan sistem ayarları (2026-11-06)
| Ayar | Dosya burada |
|---|---|
| ttyS0 giriş ekranı (getty) kaldırıldı: `/etc/service/getty-ttyS0` silindi (geri: `sudo ln -s /etc/sv/getty-ttyS0 /etc/service/`) | – |
| Yuva açma aracı `/usr/local/sbin/cpld_seri ac\|kapa\|durum` | sistem/cpld_seri.py |
| Açılışta yuvaları aç: `/etc/runit/rc-local/cpld-seri.start` | sistem/cpld-seri.start |
| WiFi sürücü güç tasarrufu kapalı: `/etc/modprobe.d/rtl8723ae.conf` | sistem/rtl8723ae.conf |
| WiFi bekçisi `/usr/local/sbin/wifi-bekci` + servis `/etc/sv/wifi-bekci/run` (kayıt `/var/log/wifi-bekci.log`) | sistem/wifi-bekci, sistem/wifi-bekci.run |

WiFi bekçisi 30 sn'de bir modemi yoklar; bağlantı yoksa: 2./4. hata `connmanctl connect`, 6./12. hata
connman yeniden başlat, 8./16. hata WiFi sürücüsünü yeniden yükle.

Çift DHCP düzeltildi (2026-11-06, `sistem/ag_duzelt.sh`): dhcpcd servisi kapatıldı (`/etc/service/dhcpcd` silindi;
geri: `sudo ln -s /etc/sv/dhcpcd /etc/service/`), connman "caner" ağında sabit 192.168.1.117 (diğer ağlarda DHCP).
DNS: /etc/resolv.conf yok (dhcpcd yazıyordu); glibc varsayılanı 127.0.0.1 = connman DNS vekili, çalışıyor.
İstenirse: `sudo ln -s /run/connman/resolv.conf /etc/resolv.conf`. connman kayıt saatleri UTC (+3 ekle).

### Dahili hoparlörler (çözülmedi)
Üstte iki hoparlör var ama ses yok; kulaklık çıkışı çalışıyor. Denenip sonuç vermeyenler (denemeler/ klasörü):
codec ALC262 hoparlör pini 0x14 (açık, %100), codec GPIO0-3, kullanılmayan pinler 0x16/0x19/0x1a/0x1b,
CPLD'de 63 bit (reset/WiFi/güç bitleri hariç), işlemci GPIO çıkışları 4/5/11. Denenmeyen: işlemci GPIO
girişleri (çatışma riski), kasa içi kablo kontrolü.

### Arkadaş paketi
`arkadas_paketi/` + `cellebrite_seri_paketi.zip`: tek komutla kurulum (`sudo sh kur.sh`, busybox),
NB12 (Tiny Core) cihazında çalıştı. Anlatım: cellebrite_seri_yuvalar.html
