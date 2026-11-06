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
| WiFi sürücü güç tasarrufu kapalı: `/etc/modprobe.d/rtl8723ae.conf` → `ips=0 swlps=0 fwlps=0` (**aspm=0 KOYMA**: açılışta PCIe köprüsünde saniyede ~68 bin kesmelik fırtına yaptı, işlemci %97 meşguldü; 2026-11-06 düzeltildi, şimdi ~12 kesme/sn, %92 boşta) | sistem/rtl8723ae.conf |
| WiFi bekçisi `/usr/local/sbin/wifi-bekci` + servis `/etc/sv/wifi-bekci/run` (kayıt `/var/log/wifi-bekci.log`) | sistem/wifi-bekci, sistem/wifi-bekci.run |

WiFi bekçisi 30 sn'de bir modemi yoklar; bağlantı yoksa: 2./4. hata `connmanctl connect`, 6./12. hata
connman yeniden başlat, 8./16. hata WiFi sürücüsünü yeniden yükle.

Çift DHCP düzeltildi (2026-11-06, `sistem/ag_duzelt.sh`): dhcpcd servisi kapatıldı (`/etc/service/dhcpcd` silindi;
geri: `sudo ln -s /etc/sv/dhcpcd /etc/service/`), connman "caner" ağında sabit 192.168.1.117 (diğer ağlarda DHCP).
DNS: /etc/resolv.conf yok (dhcpcd yazıyordu); glibc varsayılanı 127.0.0.1 = connman DNS vekili, çalışıyor.
İstenirse: `sudo ln -s /run/connman/resolv.conf /etc/resolv.conf`. connman kayıt saatleri UTC (+3 ekle).

### Ön tuşlar
Yön tuşları + OK normal klavye tuşu (X keycode: 111 yukarı, 116 aşağı, 113 sol, 114 sağ, 36 Enter). **L ve R tuşları = dahili PS/2 farenin sol (button 1) ve sağ (button 3) tuşu.** Varsayılan i8042 aktif-MUX kipinde fare bulunamıyordu; 2026-11-06'da GRUB'a `i8042.nomux=1` eklendi (`/etc/default/grub`, yedek `/etc/default/grub.yedek-2026-11-06`, sonra `sudo update-grub`). Şimdi "PS/2 Generic Mouse" (xinput id 10) olarak görünüyor.
DİKKAT: L/R, imlecin son dokunulan yerinde sol/sağ tıklama yapar. Panelde ayrı iş için kullanılacaksa `xinput set-button-map "PS/2 Generic Mouse" 8 2 9` ile 8/9 numaralı tuşlara taşınıp Tk'de `<Button-8>`/`<Button-9>` olarak yakalanabilir. Henüz bir işe atanmadı.

### Dahili hoparlörler (ÇÖZÜLDÜ 2026-11-06)
Sebep: ses yongası ALC262'nin hoparlör pini (0x14) EAPD (dış amfiyi açma sinyali) özelliğini bildirmiyor; Linux sürücüsü
bu yüzden EAPD'ye hiç dokunmuyor, amfi kapalı kalıyor (EAPD=0). Windows sürücüsü açıyordu.
Elle açma: `sudo hda-verb /dev/snd/hwC0D0 0x14 0x70c 0x02` (0x15'te de aynı etki).
Kalıcı: sürücü yaması `/lib/firmware/karavan-hoparlor.fw` (sistem/karavan-hoparlor.fw) +
`/etc/modprobe.d/karavan-ses.conf` → `options snd-hda-intel patch=karavan-hoparlor.fw` (sistem/karavan-ses.conf).
Kontrol: `cat /sys/class/sound/hwC0D0/init_verbs` → `0x14 0x70c 0x0002`. power_save=0 olduğu için kart uyuyup sıfırlamıyor.
Denenip işe yaramayanlar (denemeler/): codec GPIO (16 birleşim), VREF, kullanılmayan pinler, CPLD bitleri, SCH GPIO çıkışları.
Otomatik geçiş: jak algılaması çalışıyor ('Headphone Mic Jack'); PipeWire jak takılınca Speaker'ı kapatıp Headphone'u açıyor, çıkınca tersini yapıyor (2026-11-06 doğrulandı, ayar gerekmedi).

### Arkadaş paketi
`arkadas_paketi/` + `cellebrite_seri_paketi.zip`: tek komutla kurulum (`sudo sh kur.sh`, busybox),
NB12 (Tiny Core) cihazında çalıştı. Anlatım: cellebrite_seri_yuvalar.html
