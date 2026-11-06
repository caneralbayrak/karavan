import glob, os, sys, torch, torchaudio as ta
# Spektral kapı: her dosyanın en sessiz karelerinden gürültü profilini çıkar, onu bastır
kaynak, hedef, guc = sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
n, hop = 1024, 256
win = torch.hann_window(n)
for f in sorted(glob.glob(kaynak + '/*.wav')):
    w, sr = ta.load(f); x = w[0]
    X = torch.stft(x, n, hop, window=win, return_complex=True)
    M = X.abs()
    e = M.pow(2).sum(0)
    sessiz = e <= torch.quantile(e, 0.15)
    gurultu = M[:, sessiz].mean(1, keepdim=True) if sessiz.sum() > 3 else M.min(1, keepdim=True).values
    maske = ((M - guc * gurultu) / M.clamp_min(1e-8)).clamp(0, 1)
    # zamanda/frekansta yumuşat (müzikal gürültüyü azaltır)
    maske = torch.nn.functional.avg_pool2d(maske[None, None], (3, 5), 1, (1, 2))[0, 0]
    maske = maske.clamp_min(0.03)
    y = torch.istft(X * maske, n, hop, window=win, length=len(x))
    # yüksek geçiren (80 Hz altı uğultu)
    y = ta.functional.highpass_biquad(y, sr, 80)
    k = 10 ** (-1 / 20) / y.abs().max().clamp_min(1e-6)
    ta.save(hedef + '/' + os.path.basename(f), (y * min(k, 1.6))[None].clamp(-1, 1), sr, encoding='PCM_S', bits_per_sample=16)
