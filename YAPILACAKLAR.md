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
- [ ] Su geçirmez DS18B20'yi deponun ya da hortumların yanına koy (mevcut DS18B20 ile aynı hatta bağlanabilir)

### Basınç sensörü GY-63 / MS5611 (rakım ve fırtına uyarısı için, elde var)
- [ ] Mevcut I2C hattına bağla: SDA → **GPIO21**, SCL → **GPIO22**, VCC → 3.3V, GND
- [ ] **CSB pinini VCC'ye (3.3V) bağla!** Böylece adresi 0x76 olur. Bağlamazsan 0x77'de kalır ve BME280 ile çakışır

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

### Sonra
- [ ] ESP'ye yeni yazılımı yükle (Claude yapabilir)
- [ ] Kışın su tesisatını boşalt (akış sensörü donarsa çatlar)

## Alışveriş listesi

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
- [x] iGate için USB-RS232 GEREKMİYOR — mini PC'de RS-232 (DB9) soketi var
- (Ek GPS gerekmez: NEO-M8N TX hem ESP GPIO16'ya hem MAX3232'ye; GPS'i telsizin 10V/13.2V çıkışından doğrudan besleme)
- Sorulacak: telsiz modeli (4021/4025?), firmware yüklü ve APRS yayında denendi mi? (mini PC DB9: VAR)

### Diğer (konuşulacak, acele yok)
- [ ] Gaz / CO (MQ-6, MQ-7 elde var; karavanda pilli CO ve LPG dedektörü zaten var)

## Yazılım işleri (Claude yapacak)
- [ ] **APRS iGate köprüsü:** telsizin seri çıkışı (RS-232, APRS-IS biçiminde metin) → mini PC ttyS0 → SIM interneti varken APRS-IS'e gönderen betik
- [ ] (Sonra) Eski iPad'i panel olarak dene: web paneli eski Safari'de çalışıyor mu? Mini PC ekranı zayıf (rezistif, bazı dokunuşları kaçırıyor)
- [x] **Mini PC için tarayıcısız panel** (2026-11-01): yerel_panel/panel.py, kioskta varsayılan
- [ ] **Rakım:** GPS + MS5611 (GY-63) birleşimi; panelde rakım ve yol boyu tırmanış
- [ ] **Fırtına uyarısı:** basınç 3 saatte >3 hPa düşerse uyarı (yükseklik değişimi GPS ile ayıklanır)
- [ ] **Akü donma koruması:** akü 0 °C altındayken şarj olursa uyarı (BMS sıcaklığı)
- [ ] **Su donma uyarısı:** su/hortum sıcaklığı 0 °C'ye yaklaşınca uyarı (+ istenirse pompayı kapat)
- [x] **GPS alarmı:** alarm kuruluyken 50 m+ yer değiştirirse ntfy bildirimi (konum linkiyle) — kod yazıldı 2026-11-03
- [x] Panellerde (web + yerel) GPS konum/uydu gösterimi (2026-11-04, Genel sekmesinde Konum kartı)
