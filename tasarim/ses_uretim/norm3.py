import glob, os, sys, torchaudio as ta
HEDEF_RMS, TEPE = 10 ** (-16 / 20), 10 ** (-1 / 20)
kaynak, hedef = sys.argv[1], sys.argv[2]
for f in sorted(glob.glob(kaynak + '/*.wav')):
    w, sr = ta.load(f); w = w.mean(0, keepdim=True)
    e = (w.abs() > 0.03 * w.abs().max()).nonzero()
    w = w[:, max(0, e[0, 1] - int(0.05 * sr)): e[-1, 1] + int(0.15 * sr)]
    k = min(HEDEF_RMS / max(w.pow(2).mean().sqrt().item(), 1e-6), TEPE / max(w.abs().max().item(), 1e-6))
    w = (w * k).clamp(-1, 1)
    h = int(0.02 * sr); x = w[0]
    en = [x[i:i+h].pow(2).mean().sqrt().item() > 0.02 for i in range(0, len(x) - h, h)]
    son = max(i for i, s in enumerate(en) if s)
    w = w[:, : min(len(x), (son + 1) * h + int(0.15 * sr))]
    # şüpheli kuyruk: son ses parçası kısa ve öncesinde uzun sessizlik
    en = en[:son + 1]; seg = []; i = 0
    while i < len(en):
        j = i
        while j < len(en) and en[j] == en[i]: j += 1
        seg.append((en[i], (j - i) * 0.02)); i = j
    s = [g for g in seg if g[1] >= 0.1]
    supheli = len(s) >= 2 and s[-1][0] and s[-1][1] <= 0.5 and not s[-2][0] and s[-2][1] >= 0.5
    ta.save(hedef + '/' + os.path.basename(f), w, sr, encoding='PCM_S', bits_per_sample=16)
    if supheli: print('SUPHELI', os.path.basename(f)[:-4])
