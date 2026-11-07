import os, torch, torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
REF = '/is/fleurs/train/12921899432676779919.wav'
OUT = '/is/cikti/ek3'
S = {"aku_soguk": "Dikkat! Akü donma noktasında şarj oluyor. Şarjı durdurun."}
torch.manual_seed(1)
m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
for k, t in S.items():
    w = m.generate(t, language_id="tr", audio_prompt_path=REF, exaggeration=0.4, cfg_weight=0.5)
    ta.save(f"{OUT}/{k}.wav", w, m.sr); print(k, flush=True)
print("BITTI", flush=True)
