#pragma once
#include <cmath>

// Sensörün kendi eksenindeki eğim (derece)
inline float ham_egim(float a, float b, float c) {
  return atan2f(a, sqrtf(b * b + c * c)) * 57.29578f;
}

// Sensör eğimini karavan eğimine çevirir. Sensör kartı yüzü yukarı bakacak şekilde
// yatay monte edilmiş varsayılır.
//   on  > 0 : karavanın önü yüksek
//   yan > 0 : karavanın sağı yüksek
// yon: 0 = X oku öne, 1 = arkaya, 2 = sola, 3 = sağa
struct Egim { float on; float yan; };
inline Egim karavan_egim(float ex, float ey, int yon) {
  switch (yon) {
    case 0:  return {ex, -ey};
    case 1:  return {-ex, ey};
    case 2:  return {-ey, -ex};
    default: return {ey, ex};
  }
}

// İki GPS konumu arası mesafe (metre); kısa mesafeler için yeterince doğru
inline float mesafe_m(float lat1, float lon1, float lat2, float lon2) {
  float k = 0.01745329f;
  float x = (lon2 - lon1) * k * cosf((lat1 + lat2) * 0.5f * k);
  float y = (lat2 - lat1) * k;
  return sqrtf(x * x + y * y) * 6371000.0f;
}

// GPS konumu güvenilir mi (yeterli uydu ve iyi geometri)
inline bool gps_iyi(float uydu, float hdop, float enlem) {
  return !std::isnan(enlem) && uydu >= 5 && hdop > 0 && hdop < 3;
}

// ---------------------------------------------------------------- Savrulma (snaking)
// MPU6050 jiroskobunun dikey eksen dönme hızı (°/s) saniyede ~20 kez verilir.
// Yavaş değişen kısım (viraj, sensör kayması) üstel ortalamayla çıkarılır; geriye kalan
// salınımda ardışık zıt yönlü tepeler sayılır. Tepe > esik ve iki tepe arası 0.25-1.5 sn ise
// salınım sürüyor demektir. Şerit değiştirme 1-2 tepe yapar; savrulma 4+ tepe.
struct Salinim {
  float taban = 0;        // yavaş bileşen
  float tepe = 0;         // şu anki yarım dalganın en büyük |değeri|
  int isaret = 0;         // şu anki yarım dalganın yönü
  uint32_t son_tepe = 0;  // son geçerli tepenin zamanı (ms)
  int sayac = 0;          // ardışık geçerli tepe sayısı
  float pencere_max = 0;  // kalibrasyon için: son raporlamadan beri en büyük salınım
};

// Yeni örnek. Savrulma algılandıysa true döner.
inline bool salinim_ornek(Salinim &s, float gz, uint32_t simdi, float esik, int gereken) {
  s.taban += 0.02f * (gz - s.taban);          // ~2.5 sn zaman sabiti (20 Hz)
  float v = gz - s.taban;
  if (fabsf(v) > s.pencere_max) s.pencere_max = fabsf(v);
  int isr = v > 0.5f ? 1 : v < -0.5f ? -1 : 0;
  if (isr != 0 && isr != s.isaret) {
    // yön değişti: biten yarım dalganın tepesini değerlendir
    if (s.isaret != 0 && s.tepe >= esik) {
      uint32_t ara = simdi - s.son_tepe;
      s.sayac = (s.son_tepe && ara >= 250 && ara <= 1500) ? s.sayac + 1 : 1;
      s.son_tepe = simdi;
    } else if (s.isaret != 0) {
      s.sayac = 0;
    }
    s.isaret = isr;
    s.tepe = 0;
  }
  if (fabsf(v) > s.tepe) s.tepe = fabsf(v);
  if (s.son_tepe && simdi - s.son_tepe > 2000) s.sayac = 0;  // salınım söndü
  if (s.sayac >= gereken) { s.sayac = 0; return true; }
  return false;
}

// Tek savrulma durumu (ESPHome globals özel tip tanımadığı için burada)
inline Salinim &salinim_durum() { static Salinim s; return s; }
