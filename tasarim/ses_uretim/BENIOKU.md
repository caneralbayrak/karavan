# Sesli uyarıların üretimi

Panel sesleri (`panel/sesler/*.wav`) Chatterbox Multilingual (ResembleAI, MIT lisansı) ile üretildi.
Ses rengi için referans: Google FLEURS (tr_tr, train) kadın konuşmacı kaydı `12921899432676779919.wav` (CC-BY 4.0).

Adımlar (docker, CPU'da ~4,5 saat; ekran kartlı bilgisayarda çok daha hızlı):
1. `docker build -t karavan-tts .` (bu klasördeki Dockerfile)
2. `hepsi.py` — 218 cümleyi üretir (`cikti/yeni`). Yarıda kalırsa kaldığı yerden devam eder.
3. `norm3.py cikti/yeni cikti/son` — ses seviyesini eşitler, baş/son boşlukları kırpar, şüpheli kuyrukları listeler.
4. `temizle.py cikti/son cikti/nihai` — arka plan hışırtısını spektral kapıyla bastırır.

Ayak komutları tek cümle: `sol_arka_indir_7.wav` = "Sol arka ayağı indir, yaklaşık yedi santim."
