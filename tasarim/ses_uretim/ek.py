import os, torch, torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
REF = '/is/fleurs/train/12921899432676779919.wav'
OUT = '/is/cikti/ek'
S = {
 "kontrol": "Yola çıkmadan önce kontrol listesini tamamla.",
 "tasima_ac": "Taşıma modu açıldı. İyi yolculuklar.",
 "tasima_oto": "Karavan hareket ediyor. Taşıma modu açıldı.",
 "salinim": "Dikkat! Karavan savruluyor. Gazı yavaşça bırak, sert fren yapma.",
 "durduk": "Durduk. Vardık mı, yoksa mola mı?",
 "mola": "Mola modu. Alarm kuruluyor.",
 "mola_bitti": "Yola devam ediyoruz. Alarm kapatıldı.",
 "vardik": "Hoş geldin. Konaklama modu açılıyor.",
}
torch.manual_seed(1)
m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
for k, t in S.items():
    if os.path.exists(f"{OUT}/{k}.wav"): continue
    w = m.generate(t, language_id="tr", audio_prompt_path=REF, exaggeration=0.4, cfg_weight=0.5)
    ta.save(f"{OUT}/{k}.tmp.wav", w, m.sr); os.rename(f"{OUT}/{k}.tmp.wav", f"{OUT}/{k}.wav")
    print(k, flush=True)
print("BITTI", flush=True)
