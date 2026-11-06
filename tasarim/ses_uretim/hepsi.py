import os, torch, torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
REF = '/is/fleurs/train/12921899432676779919.wav'
OUT = '/is/cikti/yeni'
sayi = "bir iki üç dört beş altı yedi sekiz dokuz on on bir on iki on üç on dört on beş on altı on yedi on sekiz on dokuz yirmi".split(' ')
sayi = ['bir','iki','üç','dört','beş','altı','yedi','sekiz','dokuz','on','on bir','on iki','on üç','on dört','on beş','on altı','on yedi','on sekiz','on dokuz','yirmi']
S = {
 "basla": "Seviye ayarı başladı. Talimatları takip et.",
 "tamam": "Tamam.",
 "duz": "Tamam, karavan düz. Ayakları sabitleyebilirsin.",
 "veri_yok": "Sensörden veri gelmiyor.",
 "konak_ac": "Konaklama modu açıldı. Karavanın konumu takip ediliyor.",
 "konak_kapa": "Konaklama modu kapatıldı.",
 "kayma": "Dikkat! Karavanın konumu değişti. Lütfen ayakları kontrol edin.",
 "duz_kabul": "Bu konum düz olarak kaydedildi.",
 "aku_dusuk": "Akü seviyesi düşük. Lütfen şarj edin.",
 "aku_kritik": "Dikkat! Akü seviyesi kritik. Gereksiz cihazları kapatın.",
 "su_az": "Su deposu azaldı.",
 "su_dolu": "Su deposu dolu olarak kaydedildi.",
 "cm_az": "Çok az kaldı.",
 "cm_cok": "Yirmi santimden fazla.",
}
for i, s in enumerate(sayi, 1): S["cm_%d" % i] = "Yaklaşık %s santim." % s
ayak = {'sol_on': 'Sol ön', 'sol_arka': 'Sol arka', 'sag_on': 'Sağ ön', 'sag_arka': 'Sağ arka'}
isl = {'indir': 'indir', 'kaldir': 'kaldır'}
for k, a in ayak.items():
    for i, f in isl.items():
        b = "%s ayağı %s" % (a, f)
        S["%s_%s" % (k, i)] = b + "."
        S["%s_%s_az" % (k, i)] = b + ", çok az."
        S["%s_%s_cok" % (k, i)] = b + ", yirmi santimden fazla."
        for n, s in enumerate(sayi, 1):
            S["%s_%s_%d" % (k, i, n)] = "%s, yaklaşık %s santim." % (b, s)
torch.manual_seed(1)
m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
kalan = [k for k in S if not os.path.exists(f"{OUT}/{k}.wav")]
print("toplam", len(S), "kalan", len(kalan), flush=True)
for j, k in enumerate(kalan, 1):
    w = m.generate(S[k], language_id="tr", audio_prompt_path=REF, exaggeration=0.4, cfg_weight=0.5)
    ta.save(f"{OUT}/{k}.wav.tmp.wav", w, m.sr)
    os.rename(f"{OUT}/{k}.wav.tmp.wav", f"{OUT}/{k}.wav")
    print(j, len(kalan), k, flush=True)
print("BITTI", flush=True)
