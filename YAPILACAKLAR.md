# Karavan – Yapılacaklar

## Benim yapacaklarım (montaj / kablolama)

### Su pompası rölesi (kod hazır)
- [ ] 8'li röle kartının bir rölesinin girişini **GPIO25**'e bağla
- [ ] Kartın **JD-VCC köprüsünü çıkar**: VCC → ESP **3.3V**, JD-VCC → **5V**, GND ortak
- [ ] Pompanın + kablosunu rölenin **COM** ve **NO** uçlarından geçir (NC değil!)
- [ ] Pompa sigortası yerinde kalsın
- [ ] (İsteğe bağlı) COM–NO'ya paralel elle anahtar: ESP bozulursa pompayı doğrudan açmak için
- [ ] Deneme: panelde "Konaklamaya hazır" → pompa çalışmalı, "Konaklamayı bitir" → durmalı

### Su seviyesi sensörleri (kod hazır)
- [ ] Akış sensörü (YF-S201) pompa çıkışına: teflon bant, elle sık + en fazla çeyrek tur
- [ ] Akış sensörünü kelepçeyle sabitle (hortum ucunda sallanmasın)
- [ ] Akış sensörü: kırmızı → **5V**, siyah → GND, sarı − **GPIO33** −[20k]− GND (içinde ~10k var; masada tepe ~3V ölçüldü 2026-11-04). Şema: semalar/akis_sensoru.png
- [ ] XKC-Y25-V'yi deponun dışına, alttan ~7 cm yüksekliğe yapıştır
- [ ] XKC besleme: kahverengi → **5V**, mavi → GND
- [ ] Önce multimetreyle dene: sarı–GND arası su varken ~5V, yokken 0V olmalı
- [x] Bölücü: sarı − **GPIO32** −[20k]−[10k]− GND (sensörün içinde ~15k var; masada su varken 3.0V, 2026-11-03). Karavanda 5V dönüştürücüyle tekrar ölç, 3.4V'u geçmesin. Şema: semalar/seviye_sensoru.png
- [ ] İlk dolumda depoyu tam doldurup panelde "Depoyu doldurdum"a bas
- [ ] **Ölçülü kalibrasyon (karavanda, gerçek pompayla):** karavan musluğundan 5 L bidonu doldur, Claude "Su Sayac" farkından sinyal/L hesaplasın; 2-3 kez tekrarla, tutarlıysa başlangıç değeri (450) yerine yazılsın

### Sıcaklık sensörü (su donma uyarısı için, elde var)
- [ ] Su geçirmez DS18B20'yi deponun ya da hortumların yanına koy (mevcut DS18B20 ile aynı hatta bağlanabilir) — **montajda** (kullanıcının kararı 2026-11-08, breadboard'da uğraşılmayacak). Bağlanınca Claude iki sensörü adresleriyle ayırıp "Su Sicaklik" ve donma uyarısını ekler

### Basınç sensörü GY-63 / MS5611 (rakım ve fırtına uyarısı için, elde var)
- [x] Masada bağlandı (2026-11-08): I2C GPIO21/22, CSB → 3.3V → adres 0x76. Yonga aslında MS5607 (değer yarı çıkıyordu) → yapılandırmada ×2 düzeltmesi. BME280'den ~2 hPa düşük (normal)
- [x] "Deniz Seviyesi Basinc" (QNH): MS5611 + son güvenilir GPS rakımı; paneller bunu tercih ediyor (yokuşta düşmez → fırtına eğilimi yolda da doğru). GPS ilk uyduyu bulunca hesaplanmaya başlar
- [ ] Karavanda kalıcı montaj: pinleri lehimle; güneş/ısıtıcı üflemesinden uzak, içeride

### GPS (kod hazır, 2026-11-03)
- [x] NEO-M8N: VCC → 5V, GND, modülün **TX → GPIO16**, modülün **RX → GPIO17** (2026-11-03 masada denendi, çalışıyor; pinler lehimlenmeli)
- [ ] Anteni gökyüzünü görecek yere (tavan/plastik kapak altı; alüminyum altında çalışmaz)
- [x] Deneme (2026-11-04, masada): eşik panelden/MQTT'den 2 m'ye indirildi, GPS oynaması bildirimi tetikledi, link haritada açıldı. Eşik tekrar 50 m ("GPS Alarm Esik" ayarı, `sensor-dugumu/number/gps_alarm_esik/command`)

### Mini PC (sudo gereken işler, şifre: mini PC şifresi)
Ayrı terminalde `ssh karavan@192.168.1.117` ile bağlanıp sırayla:
- [x] Otomatik giriş (açılınca panel kendiliğinden gelsin):
      `printf 'default_user        karavan\nautologin_enabled   true\n' | sudo tee -a /etc/slimski.local.conf`
- [x] Broker ayarındaki yazım hatası (1883O → 1883):
      `sudo sed -i 's/^listener 1883O$/listener 1883/' /etc/mosquitto/conf.d/ag.conf && sudo sv restart mosquitto`
- [x] Deneme: `sudo reboot` → ~1-2 dk sonra ekranda panel tam ekran açılmalı
- [ ] Karavana geçince mini PC şifresini değiştir (`passwd`)
- [x] Seri yuvaları aç (2026-11-06): TARGET (sağ) = ttyS0, SOURCE (sol) = ttyS1; açılışta otomatik açılıyor. Ayrıntı: mini_pc/BENIOKU.md
- [x] ttyS0'daki giriş ekranı (getty) kalıcı kapatıldı (2026-11-06)
- [x] WiFi kopması (2026-11-06): sürücü güç tasarrufu kapatıldı + WiFi bekçisi servisi kuruldu
- [ ] **İç nem birkaç gün izlensin (2026-11-08):** MPU6050 20 Hz'e çıkınca BME280 nemi bir süre 'nan' verdi; kayıt seli kapatılıp ESP yeniden başlayınca düzeldi (%53). Tekrar olursa: MPU'yu 10 Hz'e indir ya da BME280'i ayrı I2C hattına al
- [ ] Birkaç gün sonra WiFi bekçisinin kaydına bak (`/var/log/wifi-bekci.log`): kopma oldu mu, kaç sn'de geri geldi (Claude bakar)
- [ ] **Seri yuva GND'sini doğrula:** mini PC KAPALIYKEN multimetre bip ayarında beyaz-yeşil ve kahverengi teller şasiyle (USB soketinin metali) bip veriyor mu
- [x] Çift DHCP düzeltildi (2026-11-06): dhcpcd kapatıldı, mini PC evde sabit .117; yeniden başlatma testi geçti
- [ ] (Acil değil) Kart yuvaları testi: arkadaki SD yuvasına kart takıp okunuyor mu bak; öndeki SIM yuvası (OmniKey okuyucu, modem DEĞİL) için pcscd + libccid + pcsc-tools kurup eski bir SIM'le dene
- [ ] Karavana taşınırken: karavan modeminde mini PC'ye sabit IP (ya da connman'da elle), ESP'nin broker adresini yeni ağa göre ayarla
- [x] Dahili hoparlörler çalıştı (2026-11-06): amfi EAPD sinyaliyle açılıyor, sürücü yamasıyla kalıcı. Ayrıntı: mini_pc/BENIOKU.md
- [x] Kulaklık + hoparlör otomatik geçiş (2026-11-06): jak takılınca ses jaktan (harici amfi), çıkınca dahili hoparlörden — PipeWire jak algılamasıyla kendiliğinden yapıyor, ayar gerekmedi
- [x] Ön tuşlar (2026-11-06): yön+OK klavye tuşu; L/R = dahili PS/2 fare (GRUB i8042.nomux=1), kiosk.sh'de 8/9'a taşındı (tıklama yapmıyor). Panelde görev verilecek

### Seviye ayarı (karavanda)
- [ ] **Ayaklar arası mesafeyi ölç** (şu an varsayılan 400×200 cm): ön-arka = aynı taraftaki ön ve arka ayak, sol-sağ = öndeki iki ayak; ayak milinin merkezinden merkezine, cm. Claude MQTT'ye (karavan/ayar) girer ya da web panelinden girilir
- [ ] Sensör kartı yerine takılınca: panelden **sensör yönü** (X oku öne/arkaya/sola/sağa) ve su terazisiyle düzledikten sonra **"düz kabul et"**

### Sonra
- [ ] ESP'ye yeni yazılımı yükle (Claude yapabilir)
- [ ] **2. ESP (aku-dugumu) karavanda akünün yanında (2026-11-07 takıldı):** BMS sinyali -60/-70 dBm, çalışıyor. AMA ev WiFi'si karavanda -88/-90 → veri panele gelmiyor ve ESP BMS'i tuttuğu için 1. ESP de okuyamıyor. Yapılacaklar: (1) balkona WiFi güçlendirici (hazır repeater önerildi; kullanıcının fikri ESP32-C5 köprü); (2) yazılım: WiFi/MQTT birkaç dk yoksa BMS'i bıraksın, gelince geri alsın (yüklemek için laptopla karavana git ya da USB); (3) WiFi çözülünce sensor-dugumu.yaml'dan BMS kısmını çıkar
- [ ] **Akü SOC kaymış (2026-11-07):** BMS ve Smart BMS uygulaması %98, gerçek ~%30 (13,1 V, akü üstü ekran %29,8). Aküyü 220V ile tam doldur → BMS %100'e sıfırlansın. Panele voltaja dayalı yedek uyarı eklendi (12,9 V / 12,6 V, 2 dk)
- [ ] Kışın su tesisatını boşalt (akış sensörü donarsa çatlar)
- [ ] **2. ESP32 (aynı karttan 3 tane var):** akü ve ısıtıcının yanına konacak; akü BMS Bluetooth'u (1. ESP'den buraya taşınacak, -97 dBm sorunu), ısıtıcı mavi tel, CC1101, belki gaz sensörleri. 1. ESP: eğim, hareket, GPS, su, iç sıcaklık. 1. ESP yazılımı 2026-11-04'te hafızanın ~%82'si.
- [ ] **Montaj şekli (kullanıcının kararı 2026-11-05):** PCB yok, prototip doğrudan karavana; delikli plaket + ESP'ler dişi pin yuvasında + vidalı klemensler. 12V girişine sigorta, plastik kutu, kablolara gerginlik önleyici (kelepçe). Claude her plaket için renkli yerleşim şeması çizecek.
- [ ] **Kartların yeri: akünün yanı** (kullanıcının kararı, boş yer var). Oradan kabine kablo gerekenler: BME280 (iç sıcaklık; I2C uzun kabloda sorun çıkarır → yerine DS18B20 ya da kısa kablo), PIR (görüş lazım), GPS anteni (gökyüzü), su sensörleri. MPU6050 sağlam bir yere vidalanırsa her yerde olur.
- [ ] **Işık röleleri (8'li röle kartı):** mekanik anahtarlarla birlikte çalışsın → anahtarları vavien (iki yollu) anahtarla değiştir, rölenin COM/NO/NC uçlarıyla vavien bağlantısı yap (düz paralel bağlantıda anahtar açıkken röle söndüremez). Işığın gerçek durumunu okumak için lamba hattından optokuplörle/bölücüyle geri bildirim. Röle başına ~70 mA çekiyor (akü tüketimi). Kullanıcıya göre anahtarlar 3 uçlu; vavien mi ışıklı mı belli değil → karavanda elektrik kesik iken multimetre bip testiyle iki konumda A-B/A-C/B-C ölç, fotoğraf çek.
- [ ] **Dizel ısıtıcı (Sensation, Çin malı; 433 MHz kumandası var, dijital paneli var):** (1) panel kablosundaki mavi veri telini ESP32 ile sadece dinle → durum/sıcaklık/hata kodu (github.com/timmchugh11/Chinese-Diesel-Heater---ESPHome); (2) açma/kapamayı CC1101 ile kumandayı taklit ederek yap (github.com/jakkik/DieselHeaterRF). Önce: panelin, kablonun ve fişin fotoğrafı; tel renklerini multimetreyle ölç. Panel sökülebiliyor: eve getirip içini açıp PCB üzerindeki pin yazılarına (5V/GND/TX/RX vb.) bakabiliriz (kullanıcının fikri). **Termostat:** bu modelin panelinde termostat yok (satıcı "panel değişirse olur" dedi); ESP kendi termostatını yapsın: BME280 iç sıcaklığına göre ısıtıcının gücünü kumandayla artır/azalt, sık aç-kapa yapma (buji ve karbonlanma). Uzaktan çalıştırmadan önce MQ-7 CO sensörü kurulsun.
- [ ] **Karavan fotoğraflarından çıkanlar (2026-11-07):**
  - Elektrik bölmesi: Mexxcell LiFePO4 ~200 Ah, Hegel 1000 W tam sinüs inverter, Mexxsun 40 A şarj cihazı (LiFePO4 modunda mı? kontrol), Hegel MPPT, kırmızı ayırıcılar (Panel/MPPT/Akü), AC sigorta kutusu. **Akü + kutbunda ana sigorta (ANL/MEGA) var mı? bak.** Akü üstündeki bant rulosu kaldırılsın.
  - MPPT'de RJ45/RS485 var mı? → varsa güneş gücü doğrudan okunur (gölge uyarısı kolaylaşır). Fotoğraf çekilecek.
  - **İnverter:** kullanıcı Capella paneline inverterin açma anahtarına paralel kendi anahtarını (O/I, voltmetrenin yanı) takmış → ESP için aynısına paralel röle: panelden inverter aç/kapa (boşta 10-20 W yakar). Anahtar sinyal hattı mı güç hattı mı, ölçülecek.
  - **Capella anahtarları ışıklı açma-kapama (3 uç = giriş, çıkış, LED eksi), vavien DEĞİL** (fotoğraftan tahmin, ölçüyle doğrula). Paralel röle: ESP açabilir, anahtar açıkken söndüremez. Dış aydınlatma (alarm yanıp sönme) ve Hidrofor için yeterli. Tam kontrol için anahtarlar ESP girişi olur (sonra).
  - **Tavan fanı (Berhimi):** nem/sıcaklığa göre otomatik (BME280), MOSFET ile, DC ise hız ayarı.
  - **Şofben (gazlı, bacalı):** MQ-7 CO sensörü yakınına; kışın içindeki su da boşaltılsın.
  - **Isıtıcı paneli:** renkli LCD, 5 tuş + 433 MHz kumanda. Mavi tel projesi eski 3 telli LCD'ler için; bu tip farklı protokol olabilir → panel arkasındaki tel sayısı ve renkleri.
- [ ] Proje bitince: prototip karavanda oturunca KiCad ile şema + PCB çiz, dosyaları (Gerber dahil) GitHub'a koy; başkaları kendi yaptırabilsin (kullanıcının fikri 2026-11-05)
- [ ] Yerel panel yeni görünüm: Genel (2026-11-06) ve Akü/Su/Seviye (2026-11-08: hücre çubukları, BMS kartı, büyük depo çizimi, karavan üstten görünüş + su terazisi) bitti. Sırada web paneli (panel/index.html) aynı tarza
- [x] Sesli uyarılar yenilendi (2026-11-06/07): Chatterbox + FLEURS kadın sesi, 218 dosya; ayak+santim tek cümle (sol_arka_indir_7), ses seviyesi eşit, hışırtı temizlendi. Üretim: tasarim/ses_uretim/
- [ ] Proje bitince: panellere dil seçeneği (Türkçe/İngilizce); sesli uyarılar için İngilizce Piper sesiyle ses dosyaları da üretilecek

## Alışveriş listesi

> 2026-11-06: mini PC'nin seri portu TTL çıktı → telsiz–mini PC için 2. MAX3232 gerekebilir (APRS bölümüne bak).
> 2026-11-03: YF-S201, XKC-Y25-V, NEO-M8N, MAX3232 geldi. 2026-11-04: masada GPS, seviye ve akış sensörü denendi, üçü de çalışıyor.
> 2026-11-02: siparişler verildi (telsiz fişi ve USB-RS232 kontrol sonrasına kalmıştı). Gelenleri işaretle.

### Su
- [x] 1 × YF-S201 su akış sensörü (+1 yedek) — sipariş verildi
- [x] 1 × XKC-Y25-V temassız sıvı seviye sensörü — sipariş verildi
- [ ] 12 mm hortum ↔ 1/2" diş adaptörleri (akış sensörünün iki ucu için) — yoldaki pnömatik dükkanından alınacak
- [x] Teflon bant, kelepçe — elde var
- (Dirençler, röle kartı elde var)

### GPS
- [x] 1 × NEO-M8N GPS modülü (anteniyle) — sipariş verildi

### APRS (Aselsan 4021/4025 + github.com/barisdinc/ASELSAN_4000 firmware, kılavuz bölüm 11)
- Telsizin GPS girişi RS-232 seviyesinde (TTL değil), 9600 8N1, sadece $GPRMC/$GNRMC okuyor
- [x] 1 × MAX3232 TTL↔RS-232 modülü (NEO-M8N TX → MAX3232 → telsiz) — sipariş verildi
- [x] Telsizin 8 pinli mikrofon soketine uygun fiş (pin 7 = veri girişi, pin 8 = toprak) — elde var (yoksa telsiz açılıp içeriden lehimlenecek)
      ya da arka 15 pinli opsiyon soketi fişi (pin 15 = veri girişi, pin 1 = toprak)
- [x] iGate için USB-RS232 GEREKMİYOR — mini PC'nin TARGET RJ45 yuvası seri port (ttyS0), 2026-11-06'da açıldı
- [ ] **Mini PC yuvası 3.3 V TTL (RS-232 DEĞİL!)** → telsiz ile mini PC arasına da MAX3232 lazım. Elimizdeki MAX3232'nin 2. kanalı kullanılabilir ama GPS (ESP) ile mini PC farklı yerdeyse **2. MAX3232 modülü al**. MAX3232'yi **3.3 V** ile besle. Telsizi yuvaya DOĞRUDAN bağlama (±12 V girişe zarar verir)
      Bağlantı: beyaz-mavi (TX) → MAX3232 T-IN, mavi (RX) ← MAX3232 R-OUT, beyaz-yeşil/kahverengi → GND
- (Ek GPS gerekmez: NEO-M8N TX hem ESP GPIO16'ya hem MAX3232'ye; GPS'i telsizin 10V/13.2V çıkışından doğrudan besleme)
- Sorulacak: telsiz modeli (4021/4025?), firmware yüklü ve APRS yayında denendi mi? (mini PC'de DB9 YOK; seri port RJ45 TARGET yuvası, TTL)

### Diğer (konuşulacak, acele yok)
- [ ] Gaz / CO (MQ-6, MQ-7 elde var; karavanda pilli CO ve LPG dedektörü zaten var)
- [ ] **Geri görüş kamerası (2026-11-07, karar sonra):** park sensörü yerine kamera. Öneri: hazır kablosuz set (2.4 GHz dijital, ayrı küçük ekran, "uzun menzilli"; ~2.000-5.000 TL), bizim sisteme bağlı değil → gecikme yok, sistem bozulsa da çalışır. Kamera beslemesi 13 pinli fişteki **geri vites lambası** hattından → geri vitese takınca kendiliğinden açılır. WiFi/ESP32-CAM ile telefondan izleme sürüş için önerilmez (0,5-1 sn gecikme). Alternatif: arka tampona 2-3 adet JSN-SR04T ultrasonik park sensörü (2. ESP'ye), mesafe telefondaki web panelinde + buzzer
- [ ] **Alarm çalarken dış ışıklar yanıp sönsün (kullanıcının fikri 2026-11-07):** alarm "çalıyor" durumuna geçince dış ışık(lar) ~1 sn aralıkla yanıp sönsün, alarm susunca/kapatılınca eski hâline dönsün (ışık önceden açıksa açık kalsın). Işık röleleri işine bağlı (2. ESP + vavien bağlantı). Mekanik röle sürekli yanıp sönmeye uygun değil (aşınır) → dış ışık için **MOSFET modülü** (ör. IRF520/IRLZ44N, 12V) daha iyi; ya da röle + en fazla birkaç dakika yanıp sönme sınırı. Mantık ESP'de olsun (WiFi/mini PC kopsa da çalışsın). Hangi lambaların dış ışık olduğuna karavanda bakılacak (tente lambası vb.)
- [ ] **Güvenlik kamerası (isteğe bağlı, sonra):** alarm kuruluyken PIR hareket görünce kamera fotoğraf çeksin, ntfy ile telefona göndersin (ESP32-CAM ya da mini PC'ye USB kamera)

## Yazılım işleri (Claude yapacak)
- [ ] **APRS iGate köprüsü:** telsizin seri çıkışı (RS-232, APRS-IS biçiminde metin) → MAX3232 → mini PC TARGET yuvası (ttyS0, TTL) → SIM interneti varken APRS-IS'e gönderen betik
- [ ] (Sonra) Eski iPad'i panel olarak dene: web paneli eski Safari'de çalışıyor mu? Mini PC ekranı zayıf (rezistif, bazı dokunuşları kaçırıyor)
- [x] **Mini PC için tarayıcısız panel** (2026-11-01): yerel_panel/panel.py, kioskta varsayılan
- [x] **Taşıma modu ilk sürüm (2026-11-08):** ESP: Tasima/Mola anahtarları, savrulma algılama (MPU6050 jiroskop 20 Hz, karavan.h salinim_ornek; eşik "Salinim Esik" 4 °/s, 4 tepe, ≥40 km/s; "Salinim Max" ile yolda kalibre et), hareket+300 m yol → taşıma kendiliğinden, 5 dk duruş → ntfy "Vardık/Mola" düğmeli soru (yanıt ntfy <konu>-komut'tan okunur), moladan 150 m uzaklaşınca alarm kapanır, taşımada GPS hırsızlık kontrolü yapılmaz, api/mqtt reboot_timeout 0. Paneller: Mod kutusu, kontrol listesi, Mola/Yola devam/Vardık (vardık → konaklama + seviye rehberi), 8 yeni ses. Mini PC'de dokunmayla uçtan uca denendi.
  - [ ] **Yolda ağ: karavanda MODEM ZATEN VAR (SIM hattı şu an yok — kullanıcı 2026-11-08).** Yapılacak: ESP'lere ve mini PC'ye karavan modeminin WiFi'sini ekle, modemde mini PC'ye sabit IP ver, ESP'lerin broker adresini ona göre ayarla. Hat olmasa bile modem yerel ağ kurar → panel, MQTT ve mola alarmı yolda çalışır; sadece ntfy (internet) için hat ya da telefon hotspot'u lazım. Modemin markası/modeli ve ağ adresi (192.168.x.x) öğrenilecek.
  - [ ] İlk yolculukta: "Salinim Max" değerlerine bak (düz yol / bozuk yol), eşiği ayarla; ntfy Vardık/Mola düğmelerini gerçek duruşta dene.
- [ ] **TAŞIMA MODU (kullanıcı onayladı 2026-11-07, "hepsi güzel"):** konaklama modunun karşılığı; panelde "Yola çıkıyorum" düğmesi.
  - **Hazırlık:** su pompası, inverter, ışıklar kapansın (röleler gelince); hareket alarmı ve kayma uyarısı yolda susturulsun.
  - **Sesli kontrol listesi:** ayaklar kalktı mı, tente, tavan kapağı, pencereler, gaz vanası, buzdolabı kilidi, şofben/ısıtıcı → panelde dokunarak onay.
  - **Kapı/pencere/tavan kapağı sensörleri** (mıknatıslı reed, parça alınacak): açık kalan varsa yola çıkarken uyarı.
  - **Savrulma uyarısı:** MPU6050 ile yanal salınım (snaking) algılanınca arabadaki telefona acil ntfy (öncelikli iş, donanım hazır).
  - **Lastik basıncı:** BLE TPMS sibop sensörleri (parça alınacak) → 2. ESP okur; düşük basınç/sönme → telefona bildirim.
  - **Yolculuk kaydı:** GPS'ten yol, süre, en yüksek hız, rota; yolda güneşten gelen şarj (BMS akımı; 13 pinden şarj YOK, kablo uzun/ince — kullanıcı). Varınca panelde özet.
  - **İç sıcaklık:** donma / aşırı ısınma uyarısı.
  - **Durunca soru:** hız birkaç dk sıfırda kalınca panel + telefon: "Vardık mı, moladayız mı?" → **Vardık:** konaklama moduna geç, seviye rehberi başlasın, pompa açılsın. **Moladayız:** taşıma modunda kal; karavan başında kimse yoksa hareket alarmı geçici kurulsun, yeniden yola çıkınca (GPS hızı) kendiliğinden kapansın.
  - **Unutma uyarısı:** GPS hızı birkaç dk >15 km/s ve taşıma modu kapalıysa telefona "Taşıma modunu açmayı unuttun".
- [ ] **Rakım:** GPS + MS5611 (GY-63) birleşimi; panelde rakım ve yol boyu tırmanış
- [ ] **Fırtına uyarısı:** basınç 3 saatte >3 hPa düşerse uyarı (yükseklik değişimi GPS ile ayıklanır)
- [ ] **Panel gölgede mi? uyarısı (2026-11-07):** paneller tavanda DÜZ → karavanın yönü önemsiz, sadece gölge önemli. GPS konum + tarih/saat → güneş yüksekliği → beklenen panel gücü (internet varsa bulut tahmini de); BMS'den gelen gerçek şarj akımıyla karşılaştır; hava açıkken çok düşükse "Paneller gölgede olabilir" uyarısı. Panelde gün doğumu/batımı ve öğlen güneş yüksekliği. **BMS verisine bağlı → önce 2. ESP**
- [ ] **Akü donma koruması:** akü 0 °C altındayken şarj olursa uyarı (BMS sıcaklığı)
- [ ] **Su donma uyarısı:** su/hortum sıcaklığı 0 °C'ye yaklaşınca uyarı (+ istenirse pompayı kapat)
- [x] **GPS alarmı:** alarm kuruluyken 50 m+ yer değiştirirse ntfy bildirimi (konum linkiyle) — kod yazıldı 2026-11-03
- [x] Panellerde (web + yerel) GPS konum/uydu gösterimi (2026-11-04, Genel sekmesinde Konum kartı)
