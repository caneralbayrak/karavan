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
