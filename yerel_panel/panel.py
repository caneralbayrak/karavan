#!/usr/bin/env python3
"""Karavan yerel paneli.

Mini PC'nin 800x480 dokunmatik ekranı için tarayıcısız panel (Tk ile çizilir).
Web paneliyle (panel/index.html) aynı MQTT konularını ve aynı ses dosyalarını
kullanır; telefon/dizüstündeki web panelleriyle senkron çalışır.
Ayak arası mesafe ve sensör yönü gibi klavye isteyen ayarlar web panelinden yapılır.
"""
import json
import math
import os
import queue
import struct
import subprocess
import threading
import time
import wave
import tkinter as tk

import paho.mqtt.client as mqtt

BROKER = os.environ.get('KARAVAN_BROKER', 'localhost')
DEV = 'sensor-dugumu'
AKU_DEV = 'aku-dugumu'   # 2. ESP (akünün yanı): BMS
AL_TOPIC = 'karavan/alarm'
OLAY_TOPIC = 'karavan/olay'   # ESP olayları: salinim, durdu, mola, mola_bitti, vardik, tasima_oto
AYAR_TOPIC = 'karavan/ayar'
SU_TOPIC = 'karavan/su_doldurma'
BURASI = os.path.dirname(os.path.abspath(__file__))
SES_DIR = os.path.join(BURASI, '..', 'panel', 'sesler')
SIREN = os.path.expanduser('~/.cache/karavan-siren.wav')

GECIKME = 30        # alarm kurulduktan sonra dışarı çıkmak için saniye
# Yola çıkmadan kontrol listesi
KONTROL = ('Ayaklar kaldırıldı', 'Tente kapalı', 'Tavan kapakları kapalı', 'Pencereler kapalı',
           'Gaz vanası kapalı', 'Buzdolabı kilitli', 'Dolap kapakları kapalı', 'Elektrik kablosu söküldü',
           'Su hortumu söküldü', 'Kaplin kilitli, emniyet halatı', '13 pin fiş takılı, lambalar', 'Kapı kilitli')
ESIK_CM = 1         # bundan az fark varsa köşe düz sayılır
AKU_DUSUK, AKU_KRITIK = 20, 10
# Yedek: BMS'in % sayacı kayabiliyor (2026-11-07: %98 dedi, gerçekte ~%30). LiFePO4 4S voltajı
# bu eşiklerin altında AKU_V_SURE saniye kalırsa da uyar (Webasto bujisi gibi anlık düşüşleri sayma)
AKU_V_DUSUK, AKU_V_KRITIK, AKU_V_SURE = 12.9, 12.6, 120
KARART_SN = 300    # 5 dk dokunulmazsa ekran kararır (akü tasarrufu)

# Renkler (web paneliyle aynı)
BG, KART, KENAR, YAZI, SOLUK, ESKI = '#0d1117', '#161b22', '#2a3340', '#e8edf3', '#8b96a5', '#4a5360'
YESIL, TURUNCU, MAVI, SARI, MOR = '#56d364', '#f0883e', '#79c0ff', '#e3b341', '#d2a8ff'
KIRMIZI, UYARI, SU_MAVI = '#ff7b72', '#f0b33a', '#388bfd'
DUGME, DUGME_BAS, BEKLE, SECILI = '#262e3a', '#3a4556', '#2a4a6a', '#1f6feb'
KIRMIZI_DUGME, YESIL_DUGME, TURUNCU_DUGME = '#b62324', '#1a7f37', '#9a5b00'
# Yumuşak düğmeler (Genel): koyu renkli zemin + açık renkli yazı; parlak dolgu göz almasın
Y_KIRMIZI, Y_YESIL, Y_MAVI, Y_TURUNCU = '#4a1c1f', '#183824', '#183252', '#46310f'
Y_YAZI = {Y_KIRMIZI: '#ffaba5', Y_YESIL: '#7ee2a0', Y_MAVI: '#a5cdff', Y_TURUNCU: '#ffcf73'}
KAYMA_BG, HAREKET_BG, ALARM_BG = '#4a3000', '#3a1416', '#8b1a1a'
UST_BG = '#161b22'
SIMGE_DIR = os.path.join(BURASI, 'simgeler')


def F(boy, kalin=False):
    return ('DejaVu Sans', boy, 'bold' if kalin else 'normal')


def yuvarla(x):
    """JavaScript Math.round ile aynı (0.5 yukarı)."""
    return int(math.floor(x + 0.5))


def sayi(s):
    try:
        v = float(s)
        return None if math.isnan(v) else v
    except ValueError:
        return None


# ---------------------------------------------------------------- Ses
def siren_dosyasi():
    """Web panelindeki siren: kare dalga 900 Hz, 1.5 Hz ile ±350 Hz kayan, kazanç 0.3."""
    if os.path.exists(SIREN):
        return SIREN
    os.makedirs(os.path.dirname(SIREN), exist_ok=True)
    hz, sure = 22050, 4.0          # 4 sn = 6 tam LFO turu, döngüde kesinti olmaz
    faz, veri = 0.0, bytearray()
    for i in range(int(hz * sure)):
        t = i / hz
        f = 900 + 350 * math.sin(2 * math.pi * 1.5 * t)
        faz += 2 * math.pi * f / hz
        veri += struct.pack('<h', int((1 if math.sin(faz) >= 0 else -1) * 0.3 * 32767))
    gecici = SIREN + '.tmp'
    with wave.open(gecici, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(hz)
        w.writeframes(bytes(veri))
    os.replace(gecici, SIREN)
    return SIREN


class Ses:
    """Hazır wav dosyalarını sırayla çalar (pw-play); siren ayrı döngüde çalar."""

    def __init__(self):
        self.q = queue.Queue()
        self.p = None
        self.kilit = threading.Lock()
        self.siren_acik = False
        self.siren_p = None
        threading.Thread(target=self._calis, daemon=True).start()

    def _oynat(self, yol):
        return subprocess.Popen(['pw-play', yol], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def bosalt(self):
        try:
            while True:
                self.q.get_nowait()
        except queue.Empty:
            pass

    def soyle(self, liste, kes=False):
        if kes:
            self.bosalt()
            with self.kilit:
                if self.p and self.p.poll() is None:
                    self.p.terminate()
        for k in liste:
            self.q.put(k)

    def konusuyor(self):
        with self.kilit:
            calan = self.p is not None and self.p.poll() is None
        return calan or not self.q.empty()

    def _calis(self):
        while True:
            k = self.q.get()
            yol = os.path.join(SES_DIR, k + '.wav')
            if not os.path.exists(yol):
                continue
            with self.kilit:
                self.p = p = self._oynat(yol)
            p.wait()

    def siren(self, acik):
        if acik and not self.siren_acik:
            self.siren_acik = True
            threading.Thread(target=self._siren, daemon=True).start()
        elif not acik and self.siren_acik:
            self.siren_acik = False
            p = self.siren_p
            if p and p.poll() is None:
                p.terminate()

    def _siren(self):
        yol = siren_dosyasi()
        while self.siren_acik:
            self.siren_p = self._oynat(yol)
            self.siren_p.wait()


# ---------------------------------------------------------------- Arayüz parçaları
YAKALAMA_PX = 30     # dokunuş düğmeye denk gelmezse bu kadar yakındaki düğme kabul edilir


class Dugme(tk.Label):
    """Dokunmatik düğme: basınca anında renk değiştirir; işlemi parmak kalkınca,
    o anki gerçek konumdaki düğmede yapar. Rezistif ekran bazı bölgelerde
    dokunuşu birkaç on piksel kaydırdığı için, boşluğa düşen dokunuş en yakın
    düğmeye (YAKALAMA_PX içinde) verilir."""
    hepsi = []

    def __init__(self, ust, yazi, komut, boy=13, renk=DUGME, **kw):
        super().__init__(ust, text=yazi, bg=renk, fg=Y_YAZI.get(renk, YAZI), font=F(boy), **kw)
        self.komut, self.renk = komut, renk
        self.bekliyor, self._z = False, None
        Dugme.hepsi.append(self)
        self.bind('<ButtonPress-1>', self._bas)
        self.bind('<ButtonRelease-1>', self._birak)

    def renk_ayarla(self, r):
        self.renk = r
        if not self.bekliyor:
            self.config(bg=r, fg=Y_YAZI.get(r, YAZI))

    def _bas(self, e):
        if not self.bekliyor:
            self.config(bg=DUGME_BAS)

    def _birak(self, e):
        if not self.bekliyor:
            self.config(bg=self.renk)
        w = Dugme.hedef(self, e.x_root, e.y_root)
        if w:
            w.komut()

    @staticmethod
    def gorunur(w):
        """Düğme ekranda ve üstte mi (başka sayfa/onay kutusu altında kalmamış)?"""
        if not w.winfo_ismapped():
            return False
        x, y = w.winfo_rootx() + w.winfo_width() // 2, w.winfo_rooty() + w.winfo_height() // 2
        return w.winfo_containing(x, y) is w

    @staticmethod
    def hedef(ref, X, Y):
        w = ref.winfo_containing(X, Y)
        if isinstance(w, Dugme):
            return w if w.winfo_ismapped() else None
        en, en_d = None, YAKALAMA_PX + 1
        for d in Dugme.hepsi:
            if not d.winfo_ismapped():
                continue
            x0, y0 = d.winfo_rootx(), d.winfo_rooty()
            dx = max(x0 - X, 0, X - (x0 + d.winfo_width()))
            dy = max(y0 - Y, 0, Y - (y0 + d.winfo_height()))
            uz = max(dx, dy)
            if uz < en_d and Dugme.gorunur(d):
                en, en_d = d, uz
        return en

    def bekle(self, yazi, geri_al):
        """ESP'ye komut giden düğme: yanıt gelene kadar ikinci basışı yok say."""
        if self.bekliyor:
            return False
        self.bekliyor = True
        self.config(bg=BEKLE, fg=YAZI, text=yazi)
        self._z = self.after(5000, lambda: (self.bitti(), geri_al()))
        return True

    def bitti(self):
        if self._z:
            self.after_cancel(self._z)
            self._z = None
        if self.bekliyor:
            self.bekliyor = False
            self.config(bg=self.renk, fg=Y_YAZI.get(self.renk, YAZI))


_simgeler = {}


def simge(ad, boy=22):
    """simgeler/<ad>_<boy>.png (tasarim/simge_uret.py ile üretilir); yoksa None."""
    k = (ad, boy)
    if k not in _simgeler:
        yol = os.path.join(SIMGE_DIR, '%s_%d.png' % k)
        try:
            _simgeler[k] = tk.PhotoImage(file=yol)
        except tk.TclError:
            _simgeler[k] = None
    return _simgeler[k]


def yuvarlak_noktalar(x1, y1, x2, y2, r):
    return (x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1)


def yuvarlak(c, x1, y1, x2, y2, r, **kw):
    return c.create_polygon(yuvarlak_noktalar(x1, y1, x2, y2, r), smooth=True, **kw)


class Kart(tk.Canvas):
    """Yuvarlak köşeli kart. İçine konan yazıların zemini kartla birlikte boyanır."""

    def __init__(self, ust, w, h, serit=None):
        super().__init__(ust, width=w, height=h, bg=ust.cget('bg'), highlightthickness=0, bd=0)
        self.zemin = yuvarlak(self, 1, 1, w - 2, h - 2, 14, fill=KART, outline=KENAR, width=1)
        self.serit = None
        if serit:
            self.serit = self.create_rectangle(1, 12, 5, h - 12, fill=serit, width=0)
        self.bg = KART

    def renk(self, bg, kenar=None):
        self.itemconfig(self.zemin, fill=bg, outline=kenar or (KENAR if bg == KART else bg))
        if bg != self.bg:
            self.bg = bg
            for w in self.winfo_children():
                if not isinstance(w, Dugme):
                    w.config(bg=bg)

    def serit_renk(self, r):
        if self.serit:
            self.itemconfig(self.serit, fill=r)


def kart(ust, x, y, w, h, baslik, simge_adi=None, serit=None):
    f = Kart(ust, w, h, serit)
    f.place(x=x, y=y, width=w, height=h)
    im = simge(simge_adi) if simge_adi else None
    b = tk.Label(f, text=(' ' + baslik) if im else baslik, image=im or '', compound='left',
                 bg=KART, fg=SOLUK, font=F(11), anchor='w')
    b.place(x=12, y=7)
    return f, b


def deger(ust, x, y, boy=21, kalin=True, **kw):
    l = tk.Label(ust, text='–', bg=KART, fg=YAZI, font=F(boy, kalin), anchor='w', **kw)
    l.place(x=x, y=y)
    return l


def kucuk_bilgi(ust, x, y, baslik, w=140):
    tk.Label(ust, text=baslik, bg=KART, fg=SOLUK, font=F(11), anchor='w').place(x=x, y=y)
    l = tk.Label(ust, text='–', bg=KART, fg=YAZI, font=F(13), anchor='w', justify='left', wraplength=w)
    l.place(x=x, y=y + 20)
    return l


# ---------------------------------------------------------------- Panel
class Panel:
    def __init__(self, kok):
        self.kok = kok
        self.ses = Ses()
        self.gelen = queue.Queue()
        # durum
        self.seen = {}
        self.al_durum, self.kalan, self.sayac, self.flas = 'kapali', 0, None, False
        self.konak_acik, self.kayma, self.kayma_ses, self.konak_istek = False, False, 0, None
        self.tasima, self.mola, self.durdu_soru = False, False, False
        self.aku, self.aku_zaman, self.aku_uyari = {}, 0, 0
        self.v_alt = {1: None, 2: None}   # voltaj eşiğin altına ne zaman indi
        self.bms_bagli, self.bms_baglanti, self.bms_sinyal = False, True, None
        self.su, self.su_zaman, self.su_alt, self.su_dolum, self.pompa = {}, 0, None, 0, None
        self.su_kal = '–'
        self.gps, self.gps_zaman = {}, 0
        self.egim_on = self.egim_yan = None
        self.egim_zaman = 0
        self.ayar = {'boy': 400, 'en': 200, 'yontem': 'orta'}
        self.rehber, self.hedef, self.son_ses, self.duz_say, self.veri_yok_ses = False, None, 0, 0, 0
        self.sekme_zaman = 0

        kok.configure(bg=BG)
        self._ust_cubuk()
        self.basinc_gecmis = []
        self.sayfalar = {}
        for ad in ('genel', 'aku', 'su', 'sev'):
            f = tk.Frame(kok, bg=BG)
            f.place(x=0, y=64, width=800, height=416)
            self.sayfalar[ad] = f
        self._genel(self.sayfalar['genel'])
        self._aku(self.sayfalar['aku'])
        self._su(self.sayfalar['su'])
        self._seviye(self.sayfalar['sev'])
        self._onay_kutusu()
        self._kontrol_kutusu()
        self._perde_kur()
        # Düğme dışına (yazı, kart, boşluk) düşen dokunuşlar: yakındaki düğmeye ver
        kok.bind_all('<ButtonRelease-1>', self._bosluga_dokunus, add='+')
        self.sekme('genel')
        self.konak_goster()
        self.al_goster()

        # MQTT
        self.cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='karavan-yerel-panel-%d' % os.getpid())
        self.cl.on_connect = self._baglandi
        self.cl.on_disconnect = lambda *a: self.gelen.put(('_durum', 'bağlantı yok'))
        self.cl.on_message = lambda c, u, m: self.gelen.put((m.topic, m.payload.decode('utf-8', 'replace')))
        self.cl.reconnect_delay_set(1, 5)
        self.cl.connect_async(BROKER, 1883, keepalive=30)
        self.cl.loop_start()

        self._isle()
        self.kok.after(1000, self._saniyede)
        self.kok.after(5000, self._bes_saniyede)
        self.kok.after(30000, self._otuz_saniyede)

    # ---------------- üst çubuk ve sekmeler
    def _ust_cubuk(self):
        u = tk.Frame(self.kok, bg=UST_BG)
        u.place(x=0, y=0, width=800, height=62)
        tk.Frame(u, bg=KENAR).place(x=0, y=61, width=800, height=1)
        self.sekme_d = {}
        for i, (ad, yazi, sm) in enumerate((('genel', 'Genel', 'genel'), ('aku', 'Akü', 'aku'),
                                            ('su', 'Su', 'su'), ('sev', 'Seviye', 'seviye'))):
            d = Dugme(u, yazi, lambda a=ad: (self.sekme(a), setattr(self, 'sekme_zaman', time.time())), boy=15)
            im = simge(sm, 26)
            if im:
                d.config(image=im, compound='left', text='  ' + yazi)
            d.place(x=6 + i * 150, y=6, width=144, height=50)
            self.sekme_d[ad] = d
        self.saat = tk.Label(u, text='', bg=UST_BG, fg=YAZI, font=F(20, True), anchor='e')
        self.saat.place(x=640, y=4, width=152)
        self.st = tk.Label(u, text='● bağlanıyor', bg=UST_BG, fg=SOLUK, font=F(9), anchor='e')
        self.st.place(x=640, y=38, width=152)

    # ---------------- ekran karartma
    # Kararmayı X'e bırakmıyoruz: X kararmış ekranı açan dokunuşu panele de
    # iletiyor ve parmağın altındaki düğmeye basılıyordu. Panel kendisi karartır;
    # ekranın üstüne siyah bir perde koyar, uyandıran dokunuş perdeye gider.
    def _perde_kur(self):
        self.son_dokunus, self.karanlik = time.time(), False
        self.perde = tk.Frame(self.kok, bg='black', cursor='none')
        self.perde.bind('<ButtonPress-1>', lambda e: self.uyan())
        self.kok.bind_all('<ButtonPress-1>', lambda e: setattr(self, 'son_dokunus', time.time()), add='+')
        self._xset('s', 'off')      # X'in kendi karartmasını kapat

    @staticmethod
    def _xset(*a):
        try:
            subprocess.Popen(('xset',) + a, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def karart(self):
        if self.karanlik:
            return
        self.karanlik = True
        self.perde.place(x=0, y=0, width=self.kok.winfo_width(), height=self.kok.winfo_height())
        self.perde.tkraise()
        self._xset('s', 'activate')     # arka ışığı/ekranı kapat

    def uyan(self):
        self.son_dokunus = time.time()
        if not self.karanlik:
            return
        self.karanlik = False
        self.perde.place_forget()
        self._xset('s', 'reset')

    def _bosluga_dokunus(self, e):
        if e.widget is self.perde:
            return      # ekranı uyandıran dokunuş, düğmeye basma
        if isinstance(e.widget, Dugme):
            return      # düğmenin kendi işleyicisi halletti
        w = Dugme.hedef(self.kok, e.x_root, e.y_root)
        if w:
            w.komut()

    def sekme(self, ad):
        self.aktif = ad
        self.sayfalar[ad].tkraise()
        for a, d in self.sekme_d.items():
            d.renk_ayarla(SECILI if a == ad else DUGME)

    def sor(self, metin, evet, evet_yazi='Evet', hayir_yazi='Vazgeç', hayir=None):
        self.sor_evet, self.sor_hayir = evet, hayir
        self.sor_m.config(text=metin)
        self.sor_e.config(text=evet_yazi)
        self.sor_h.config(text=hayir_yazi)
        self.sor_f.place(x=0, y=0, width=800, height=480)
        self.sor_f.tkraise()

    def _onay_kutusu(self):
        self.sor_evet = self.sor_hayir = None
        f = tk.Frame(self.kok, bg='#080808')
        k = tk.Frame(f, bg=KART, highlightthickness=1, highlightbackground=KENAR)
        k.place(x=130, y=130, width=540, height=200)
        self.sor_m = tk.Label(k, text='', bg=KART, fg=YAZI, font=F(15), wraplength=500, justify='left')
        self.sor_m.place(x=18, y=14)

        def kapat(evet):
            self.durdu_soru = False
            f.place_forget()
            fn = self.sor_evet if evet else self.sor_hayir
            self.sor_evet = self.sor_hayir = None
            if fn:
                fn()
        self.sor_h = Dugme(k, 'Vazgeç', lambda: kapat(False), boy=16)
        self.sor_h.place(x=18, y=118, width=240, height=62)
        self.sor_e = Dugme(k, 'Evet', lambda: kapat(True), boy=16, renk=YESIL_DUGME)
        self.sor_e.place(x=280, y=118, width=240, height=62)
        self.sor_f = f

    # ---------------- Yola çıkış kontrol listesi
    def _kontrol_kutusu(self):
        f = tk.Frame(self.kok, bg=BG)
        tk.Label(f, text='Yola çıkmadan kontrol et', bg=BG, fg=YAZI, font=F(16, True), anchor='w').place(x=16, y=8)
        self.kontrol_d = []
        for i, m in enumerate(KONTROL):
            d = Dugme(f, '', None, boy=13, anchor='w', padx=12)
            d.komut = (lambda d=d: self._kontrol_isaretle(d))
            d.metin, d.tamam = m, False
            d.place(x=12 + (i % 2) * 392, y=46 + (i // 2) * 56, width=384, height=50)
            self.kontrol_d.append(d)
        Dugme(f, 'Vazgeç', lambda: f.place_forget(), boy=15).place(x=12, y=400, width=250, height=70)
        self.kontrol_t = Dugme(f, 'Yola çık', self._kontrol_bitti, boy=16, renk=SECILI)
        self.kontrol_t.place(x=278, y=400, width=510, height=70)
        self.kontrol_f = f

    def _kontrol_isaretle(self, d):
        d.tamam = not d.tamam
        d.config(text=('✔  ' if d.tamam else '○  ') + d.metin, fg=YESIL if d.tamam else YAZI)
        d.renk_ayarla('#16301f' if d.tamam else DUGME)
        eksik = sum(not x.tamam for x in self.kontrol_d)
        self.kontrol_t.config(text='Yola çık' if not eksik else 'Yola çık (%d eksik)' % eksik)

    def kontrol_ac(self):
        for d in self.kontrol_d:
            d.tamam = True
            self._kontrol_isaretle(d)      # hepsini "yapılmadı" yap
        self.kontrol_f.place(x=0, y=0, width=800, height=480)
        self.kontrol_f.tkraise()
        self.ses.soyle(['kontrol'], True)

    def _kontrol_bitti(self):
        eksik = [d.metin for d in self.kontrol_d if not d.tamam]

        def basla():
            self.kontrol_f.place_forget()
            self.yayinla(DEV + '/switch/tasima/command', 'ON')
            if self.al_durum != 'kapali':
                self.al_ayarla('kapali', True)
            self.ses.soyle(['tasima_ac'], True)
        if eksik:
            self.sor('İşaretlenmeyen %d madde var:\n%s\nYine de yola çıkılsın mı?' % (len(eksik), ', '.join(eksik[:4]) + ('…' if len(eksik) > 4 else '')),
                     basla, evet_yazi='Yine de çık', hayir_yazi='Geri dön')
        else:
            basla()

    # ---------------- Genel
    def _genel(self, s):
        self.d, self.d_kart = {}, {}
        for i, (k, bas, sm, sr) in enumerate((('ic', 'İç sıcaklık', 'ic', YESIL), ('nem', 'İç nem', 'nem', SU_MAVI),
                                              ('dis', 'Dış sıcaklık', 'dis', MAVI), ('bas', 'Basınç', 'basinc', MOR))):
            f, _ = kart(s, 8 + i * 197, 6, 190, 92, bas, sm, serit=sr)
            self.d[k] = deger(f, 14, 38, boy=24)
            self.d_kart[k] = f
        self.bas_e = tk.Label(self.d_kart['bas'], text='', bg=KART, fg=SOLUK, font=F(10), anchor='e')
        self.bas_e.place(x=96, y=10, width=82)
        self.hr_f, _ = kart(s, 8, 106, 255, 212, 'Hareket', 'hareket')
        self.hr = deger(self.hr_f, 14, 50, boy=36)
        self.hr_a = tk.Label(self.hr_f, text='', bg=KART, fg=SOLUK, font=F(11), anchor='w')
        self.hr_a.place(x=16, y=110)
        self.al_f, _ = kart(s, 271, 106, 255, 212, 'Alarm', 'alarm')
        self.al_l = deger(self.al_f, 14, 44, boy=26)
        self.ab = Dugme(self.al_f, 'Alarmı kur', self.alarm_dugme, boy=15, renk=Y_KIRMIZI)
        self.ab.place(x=14, y=144, width=227, height=54)
        self.konak_f, _ = kart(s, 534, 106, 258, 212, 'Mod', 'konak')
        self.konak_l = deger(self.konak_f, 14, 40, boy=24)
        self.kb = Dugme(self.konak_f, 'Konaklamaya hazır', self.konak_dugme, boy=15, renk=Y_YESIL)
        self.kb.place(x=14, y=144, width=230, height=54)
        # üst düğme: Yola çıkıyorum / Mola / Yola devam (kayma varken yerine "yeni konumu kaydet")
        self.mb = Dugme(self.konak_f, 'Yola çıkıyorum', self.yol_dugme, boy=14, renk=Y_MAVI)
        self.kk = Dugme(self.konak_f, 'Kontrol ettim, yeni\nkonumu kaydet', self.konak_yeni, boy=13)
        self.kk_yer = dict(x=14, y=86, width=230, height=52)
        # alt şerit: akü, su, konum özeti
        f, _ = kart(s, 8, 326, 255, 84, 'Akü', 'aku')
        self.oz_aku = tk.Label(f, text='–', bg=KART, fg=YAZI, font=F(17, True), anchor='e')
        self.oz_aku.place(x=150, y=6, width=92)
        self.oz_aku_c = tk.Canvas(f, width=227, height=12, bg=KART, highlightthickness=0)
        self.oz_aku_c.place(x=14, y=40)
        yuvarlak(self.oz_aku_c, 0, 0, 226, 11, 6, fill='#26303c', width=0)
        self.oz_aku_r = yuvarlak(self.oz_aku_c, 0, 0, 0, 11, 6, fill=YESIL, width=0)
        self.oz_aku_a = tk.Label(f, text='', bg=KART, fg=SOLUK, font=F(9), anchor='w')
        self.oz_aku_a.place(x=14, y=58)
        f, _ = kart(s, 271, 326, 255, 84, 'Temiz su', 'su')
        self.oz_su = tk.Label(f, text='–', bg=KART, fg=YAZI, font=F(17, True), anchor='e')
        self.oz_su.place(x=150, y=6, width=92)
        self.oz_su_c = tk.Canvas(f, width=227, height=12, bg=KART, highlightthickness=0)
        self.oz_su_c.place(x=14, y=40)
        yuvarlak(self.oz_su_c, 0, 0, 226, 11, 6, fill='#26303c', width=0)
        self.oz_su_r = yuvarlak(self.oz_su_c, 0, 0, 0, 11, 6, fill=SU_MAVI, width=0)
        self.oz_su_a = tk.Label(f, text='', bg=KART, fg=SOLUK, font=F(9), anchor='w')
        self.oz_su_a.place(x=14, y=58)
        f, _ = kart(s, 534, 326, 258, 84, 'Konum', 'konum')
        self.g_l = deger(f, 14, 32, boy=15)
        self.g_k = tk.Label(f, text='', bg=KART, fg=SOLUK, font=F(9), anchor='w')
        self.g_k.place(x=14, y=58)

    # ---------------- Akü
    def _aku(self, s):
        # büyük doluluk kartı
        f, self.aku_b = kart(s, 8, 6, 380, 200, 'Akü', 'aku', serit=YESIL)
        self.aku_f = f
        self.soc = deger(f, 16, 34, boy=46)
        self.aku_dl = tk.Label(f, text='', bg=KART, fg=SOLUK, font=F(13), anchor='e')
        self.aku_dl.place(x=180, y=56, width=184)
        self.bar = tk.Canvas(f, width=350, height=26, bg=KART, highlightthickness=0)
        self.bar.place(x=14, y=112)
        yuvarlak(self.bar, 0, 0, 349, 25, 12, fill='#26303c', width=0)
        self.bar_r = yuvarlak(self.bar, 0, 0, 0, 25, 12, fill=YESIL, width=0)
        for i in (1, 2, 3):   # %25'lik çizgiler
            self.bar.create_line(350 * i // 4, 4, 350 * i // 4, 22, fill='#0d1117', width=2)
        self.aku_k = tk.Label(f, text='', bg=KART, fg=YAZI, font=F(13), anchor='w')
        self.aku_k.place(x=16, y=148)
        self.aku_s = tk.Label(f, text='', bg=KART, fg=SOLUK, font=F(12), anchor='e')
        self.aku_s.place(x=180, y=148, width=184)
        # dört ölçüm kartı
        self.a, self.a_kart = {}, {}
        for i, (k, bas, sm, sr) in enumerate((('v', 'Voltaj', 'volt', SARI), ('a', 'Akım', 'akim', MAVI),
                                              ('w', 'Güç', 'guc', TURUNCU), ('t', 'Sıcaklık', 'ic', YESIL))):
            kf, _ = kart(s, 396 + (i % 2) * 200, 6 + (i // 2) * 104, 196, 96, bas, sm, serit=sr)
            self.a[k] = deger(kf, 14, 40, boy=22)
            self.a_kart[k] = kf
        # hücreler
        f, _ = kart(s, 8, 214, 520, 128, 'Hücreler', 'hucre')
        self.hc = tk.Canvas(f, width=496, height=92, bg=KART, highlightthickness=0)
        self.hc.place(x=12, y=32)
        self.hucre = []
        for i in range(4):
            x = i * 124
            yuvarlak(self.hc, x, 0, x + 112, 26, 8, fill='#26303c', width=0)
            r = yuvarlak(self.hc, x, 0, x, 26, 8, fill=YESIL, width=0)
            t = self.hc.create_text(x + 56, 46, text='–', fill=YAZI, font=F(13, True))
            self.hc.create_text(x + 56, 72, text='%d. hücre' % (i + 1), fill=SOLUK, font=F(9))
            self.hucre.append((r, t, x))
        self.hc_fark = tk.Label(f, text='', bg=KART, fg=SOLUK, font=F(11), anchor='e')
        self.hc_fark.place(x=300, y=8, width=206)
        # BMS bilgisi
        f, _ = kart(s, 536, 214, 256, 128, 'BMS', 'bms')
        self.bms_l = tk.Label(f, text='', bg=KART, fg=YAZI, font=F(12), anchor='nw', justify='left')
        self.bms_l.place(x=14, y=36)
        self.bb = Dugme(s, "Telefon uygulaması için Bluetooth'u bırak", self.bt_dugme, boy=14)
        self.bb.place(x=8, y=350, width=784, height=58)

    # ---------------- Su
    def _su(self, s):
        self.su_f, _ = kart(s, 8, 6, 250, 404, 'Temiz su', 'su', serit=SU_MAVI)
        f = self.su_f
        self.tank = tk.Canvas(f, width=226, height=352, bg=KART, highlightthickness=0)
        self.tank.place(x=12, y=40)
        self.TX0, self.TY0, self.TX1, self.TY1 = 48, 6, 178, 340
        yuvarlak(self.tank, self.TX0, self.TY0, self.TX1, self.TY1, 18, fill='#141b24', outline='#3a4556', width=3)
        self.tank_r = yuvarlak(self.tank, self.TX0 + 4, self.TY1 - 4, self.TX1 - 4, self.TY1 - 4, 14, fill=SU_MAVI, width=0)
        for yz in (25, 50, 75):
            y = self.TY1 - (self.TY1 - self.TY0) * yz / 100
            self.tank.create_line(self.TX1 - 22, y, self.TX1 - 4, y, fill='#5a6573', width=2)
            self.tank.create_text(self.TX1 + 8, y, text='%d' % yz, fill=SOLUK, font=F(9), anchor='w')
        self.tank_y = self.tank.create_text((self.TX0 + self.TX1) // 2, (self.TY0 + self.TY1) // 2, text='', fill=YAZI, font=F(20, True))
        # büyük değer
        kf, _ = kart(s, 266, 6, 526, 96, 'Kalan su', None)
        self.sul = deger(kf, 14, 30, boy=34)
        self.su_dl = tk.Label(kf, text='', bg=KART, fg=SOLUK, font=F(13), anchor='e')
        self.su_dl.place(x=250, y=44, width=260)
        # üç küçük kart
        self.s_kart = {}
        for i, (k, bas, sm) in enumerate((('a', 'Akış', 'akis'), ('d', 'Dolduruldu', 'takvim'), ('p', 'Pompa', 'pompa'))):
            kf, _ = kart(s, 266 + i * 178, 110, 170, 86, bas, sm, serit=KENAR if k == 'p' else None)
            setattr(self, 's_' + k, deger(kf, 14, 38, boy=17))
            self.s_kart[k] = kf
        self.sdb = Dugme(s, 'Depoyu doldurdum', self.depo_dolu, boy=15, renk=YESIL_DUGME)
        self.sdb.place(x=266, y=204, width=259, height=62)
        self.spb = Dugme(s, 'Pompayı aç', self.pompa_dugme, boy=15)
        self.spb.place(x=533, y=204, width=259, height=62)
        kf, _ = kart(s, 266, 274, 526, 136, 'Kalibrasyon', 'ayar')
        self.s_k = tk.Label(kf, text='', bg=KART, fg=SOLUK, font=F(11), anchor='nw', justify='left', wraplength=500)
        self.s_k.place(x=14, y=34)
        Dugme(kf, 'Kalibrasyon kaydını sıfırla', self.kal_sifirla, boy=12).place(x=14, y=86, width=260, height=40)

    # ---------------- Seviye
    def _seviye(self, s):
        f, _ = kart(s, 8, 6, 250, 404, 'Karavan (üstten)', 'karavan')
        self.sev_f = f
        c = tk.Canvas(f, width=232, height=362, bg=KART, highlightthickness=0)
        c.place(x=9, y=36)
        # çeki demiri + kriko tekeri
        c.create_line(116, 6, 92, 44, fill='#6b7685', width=4, capstyle='round')
        c.create_line(116, 6, 140, 44, fill='#6b7685', width=4, capstyle='round')
        c.create_oval(108, 0, 124, 14, fill='#2a3340', outline='#8b96a5', width=2)
        c.create_oval(98, 22, 110, 34, fill='#11161d', outline='#6b7685', width=2)
        # tekerlekler (aks ortada)
        for x in (8, 210):
            yuvarlak(c, x, 176, x + 14, 236, 5, fill='#0b0f14', outline='#3a4556', width=2)
            for yy in (186, 196, 206, 216, 226):
                c.create_line(x + 3, yy, x + 11, yy, fill='#2a3340')
        # gövde: dış çerçeve + iç zemin
        yuvarlak(c, 20, 40, 212, 358, 26, fill='#1b2431', outline='#4a5668', width=3)
        yuvarlak(c, 28, 48, 204, 350, 20, fill='#151d28', outline='', width=0)
        # ön ve arka cam
        yuvarlak(c, 64, 44, 168, 52, 4, fill='#2b4a6e', width=0)
        yuvarlak(c, 74, 346, 158, 354, 4, fill='#4a2b2b', width=0)
        c.create_text(116, 62, text='ÖN', fill='#6b7685', font=F(9, True))
        self.kose = {}
        yer = {'sol_on': (30, 72), 'sag_on': (120, 72), 'sol_arka': (30, 278), 'sag_arka': (120, 278)}
        adlar = {'sol_on': 'Sol ön', 'sag_on': 'Sağ ön', 'sol_arka': 'Sol arka', 'sag_arka': 'Sağ arka'}
        for k, (x, y) in yer.items():
            r = yuvarlak(c, x, y, x + 82, y + 62, 12, fill='#222a35', outline='#222a35', width=3)
            n = c.create_text(x + 41, y + 15, text=adlar[k], fill='#aab4c0', font=F(10))
            t = c.create_text(x + 41, y + 42, text='–', fill=YESIL, font=F(14, True))
            self.kose[k] = (r, t)
        # su terazisi: kırmızı / sarı / yeşil halkalar
        self.bx, self.by = 116, 206
        c.create_oval(self.bx - 62, self.by - 62, self.bx + 62, self.by + 62, fill='#2a1517', outline='#5a2a2c', width=2)
        c.create_oval(self.bx - 44, self.by - 44, self.bx + 44, self.by + 44, fill='#2a2412', outline='#5a4a1c', width=2)
        c.create_oval(self.bx - 22, self.by - 22, self.bx + 22, self.by + 22, fill='#12301d', outline='#2f8a4f', width=2)
        c.create_line(self.bx - 62, self.by, self.bx + 62, self.by, fill='#3a4556', dash=(3, 3))
        c.create_line(self.bx, self.by - 62, self.bx, self.by + 62, fill='#3a4556', dash=(3, 3))
        for d, yz in ((22, '0,6°'), (44, '2,5°')):
            c.create_text(self.bx + 14, self.by - d + 7, text=yz, fill='#8b96a5', font=F(7), anchor='w')
        self.dot_g = c.create_oval(self.bx - 15, self.by - 15, self.bx + 15, self.by + 15, fill='', outline=YESIL, width=2)
        self.dot = c.create_oval(self.bx - 11, self.by - 11, self.bx + 11, self.by + 11, fill=YESIL, outline='#0d1117', width=2)
        self.dot_p = c.create_oval(self.bx - 6, self.by - 7, self.bx - 1, self.by - 3, fill='#ffffff', width=0)
        self.nabiz, self.nabiz_k = False, None
        self.kok.after(600, self._sev_nabiz)
        self.sev_c = c
        # talimat
        self.tal_f, _ = kart(s, 266, 6, 526, 112, 'Ne yapmalı', 'rehber', serit=YESIL)
        self.talimat = tk.Label(self.tal_f, text='–', bg=KART, fg=YAZI, font=F(19, True), anchor='w', justify='left', wraplength=490)
        self.talimat.place(x=16, y=34)
        self.egimler = tk.Label(self.tal_f, text='', bg=KART, fg=SOLUK, font=F(11), anchor='w', justify='left', wraplength=490)
        self.egimler.place(x=16, y=78)
        self.rb = Dugme(s, 'Sesli seviye ayarını başlat', lambda: self.rehber_ayarla(not self.rehber), boy=16, renk=SECILI)
        self.rb.place(x=266, y=126, width=526, height=66)
        self.yb = Dugme(s, '', self.yontem_dugme, boy=13)
        self.yb.place(x=266, y=200, width=526, height=52)
        self.dk = Dugme(s, 'Bu konumu düz kabul et (sıfırla)', self.duz_kabul, boy=13)
        self.dk.place(x=266, y=260, width=526, height=52)
        kf, _ = kart(s, 266, 320, 526, 90, 'Ölçüler', 'ayar')
        self.olcu = tk.Label(kf, text='', bg=KART, fg=SOLUK, font=F(11), anchor='nw', justify='left', wraplength=500)
        self.olcu.place(x=14, y=34)
        self.ayar_goster()

    # ================================================================ MQTT
    def _baglandi(self, c, u, flags, rc, props=None):
        if rc != 0:
            return
        for t in (AL_TOPIC, AYAR_TOPIC, SU_TOPIC, OLAY_TOPIC, DEV + '/sensor/+/state', DEV + '/binary_sensor/+/state',
                  DEV + '/switch/+/state', DEV + '/text_sensor/su_kalibrasyon/state', DEV + '/number/+/state',
                  AKU_DEV + '/+/+/state'):
            c.subscribe(t)
        self.gelen.put(('_durum', 'bağlı'))

    def yayinla(self, konu, mesaj, kalici=False):
        self.cl.publish(konu, mesaj, retain=kalici)

    def _isle(self):
        try:
            for _ in range(200):
                t, s = self.gelen.get_nowait()
                try:
                    self.mesaj(t, s)
                except Exception as e:  # tek mesajdaki hata paneli durdurmasın
                    print('mesaj hatası', t, e, flush=True)
        except queue.Empty:
            pass
        self.kok.after(40, self._isle)

    def mesaj(self, t, s):
        if t == '_durum':
            self.st.config(text='● ' + s, fg=YESIL if s == 'bağlı' else KIRMIZI)
            return
        p = t.split('/')
        if t == OLAY_TOPIC:
            self.olay(s)
            return
        if t == AL_TOPIC:
            if s != self.al_durum and s in ('kapali', 'kurulu', 'caliyor'):
                self.al_ayarla(s, False)
            return
        if t == AYAR_TOPIC:
            try:
                self.ayar.update(json.loads(s))
            except ValueError:
                pass
            self.ayar_goster()
            self.seviye_goster()
            return
        if t == SU_TOPIC:
            try:
                self.su_dolum = int(s)
            except ValueError:
                self.su_dolum = 0
            self.su_goster()
            return
        if len(p) < 3:
            return
        ad = p[2]
        if ad.startswith('gps_'):
            self.gps[ad] = sayi(s)
            self.gps_zaman = time.time()
            self.gps_goster()
            return
        if ad.startswith('su_'):
            if ad == 'su_kalibrasyon':
                self.su_kal = s
            elif ad == 'su_pompasi':
                self.pompa = (s == 'ON')
            elif ad == 'su_alt_seviye':
                w = (s == 'ON')
                if self.su_alt is True and not w:   # sadece su varken yok olunca konuş
                    self.ses.soyle(['su_az'])
                self.su_alt = w
            else:
                v = sayi(s)
                if v is None:
                    return
                self.su[ad] = v
                if ad == 'su_kalan':
                    self.su_zaman = time.time()
            self.su_goster()
            return
        if p[1] == 'sensor' and ad in ('egim_on_arka', 'egim_sol_sag'):
            v = sayi(s)
            if v is None:
                return
            if ad == 'egim_on_arka':
                self.egim_on = v
            else:
                self.egim_yan = v
            self.egim_zaman = time.time()
            if self.aktif == 'sev' or self.rehber:
                self.seviye_goster()
            return
        if ad == 'bms_sinyal':
            self.bms_sinyal = sayi(s)
            self.aku_goster()
            return
        if ad.startswith('aku_') or ad in ('bms_bagli', 'bms_baglanti'):
            if ad == 'bms_bagli':
                self.bms_bagli = (s == 'ON')
            elif ad == 'bms_baglanti':
                self.bms_baglanti = (s == 'ON')
            elif ad == 'aku_durum':
                self.aku['durum'] = s
            elif ad == 'aku_hatalar':
                self.aku['hatalar'] = s
            elif p[1] == 'sensor':
                v = sayi(s)
                if v is None:
                    return
                self.aku[ad] = v
                self.aku_zaman = time.time()
                if ad in ('aku_doluluk', 'aku_voltaj'):
                    self.aku_ses_kontrol()
            else:
                return
            self.aku_goster()
            return
        if p[1] == 'switch' and ad in ('tasima', 'mola') and p[0] == DEV:
            setattr(self, ad, s == 'ON')
            # Soru telefondan / başka panelden yanıtlandıysa açık kutuyu kapat
            if self.durdu_soru and (not self.tasima or self.mola):
                self.durdu_soru = False
                self.sor_f.place_forget()
                self.sor_evet = self.sor_hayir = None
            self.konak_goster()
            return
        if p[1] == 'switch' and ad == 'konaklama':
            self.konak_acik = (s == 'ON')
            # sadece bu panelden basıldıysa konuş (açılışta konuşmasın)
            if self.konak_istek is not None and self.konak_istek == self.konak_acik:
                self.ses.soyle(['konak_ac' if self.konak_acik else 'konak_kapa'], True)
                self.konak_istek = None
            self.konak_goster()
            return
        if p[1] == 'binary_sensor' and ad == 'kayma':
            yeni = (s == 'ON')
            if yeni and not self.kayma:
                self.ses.soyle(['kayma'], True)
                self.kayma_ses = time.time()
                self.sekme('genel')
                self.uyan()
            self.kayma = yeni
            self.konak_goster()
            return
        bicim = {'ic_sicaklik': ('ic', 1, ' °C'), 'ic_nem': ('nem', 0, ' %'),
                 'basinc': ('bas', 0, ' hPa'), 'dis_sicaklik': ('dis', 1, ' °C')}
        if p[1] == 'sensor' and ad in bicim:
            k, d, b = bicim[ad]
            v = sayi(s)
            if v is None:
                return
            renk = YAZI
            if k in ('ic', 'dis'):
                renk = MAVI if v < 10 else TURUNCU if v > 27 else YESIL
                self.d_kart[k].serit_renk(renk)
            elif k == 'bas':
                self.basinc_egilim(v)
            self.d[k].config(text=('%.' + str(d) + 'f') % v + b, fg=renk)
            self.seen[k] = time.time()
        elif p[1] == 'binary_sensor' and ad == 'hareket':
            on = (s == 'ON')
            self.hr.config(text='VAR' if on else 'yok', fg=KIRMIZI if on else SOLUK)
            self.hr_f.renk(HAREKET_BG if on else KART, KIRMIZI if on else None)
            if on:
                self.hr_a.config(text='son: ' + time.strftime('%H:%M'))
            if on and self.al_durum == 'kurulu':
                self.al_ayarla('caliyor', True)

    # ================================================================ Alarm
    def al_goster(self):
        y = {'kapali': 'kapalı', 'bekliyor': 'çıkış: %d sn' % self.kalan, 'kurulu': 'KURULU', 'caliyor': 'ALARM!'}
        r = {'kapali': SOLUK, 'bekliyor': SARI, 'kurulu': TURUNCU, 'caliyor': '#fff'}
        self.al_l.config(text=y[self.al_durum], fg=r[self.al_durum])
        self.ab.config(text='Alarmı kur' if self.al_durum == 'kapali' else 'Alarmı kapat')
        self.ab.renk_ayarla(Y_KIRMIZI if self.al_durum == 'kapali' else DUGME)
        if self.al_durum != 'caliyor':
            self._al_renk(KART)

    def _al_renk(self, r):
        self.al_f.renk(r, TURUNCU if r == KART and self.al_durum == 'kurulu' else None)

    def _flas(self):
        if self.al_durum != 'caliyor':
            return
        self.flas = not self.flas
        self._al_renk(ALARM_BG if self.flas else KART)
        self.kok.after(400, self._flas)

    def al_ayarla(self, d, yayin):
        if d == 'caliyor':
            self.sekme('genel')
            self.uyan()
        if self.sayac and d != 'bekliyor':
            self.kok.after_cancel(self.sayac)
            self.sayac = None
        onceki, self.al_durum = self.al_durum, d
        self.ses.siren(d == 'caliyor')
        if yayin and d != 'bekliyor':
            self.yayinla(AL_TOPIC, d, True)
        self.al_goster()
        if d == 'caliyor' and onceki != 'caliyor':
            self._flas()

    def _geri_say(self):
        self.kalan -= 1
        if self.kalan <= 0:
            self.sayac = None
            self.al_ayarla('kurulu', True)
        else:
            self.al_goster()
            self.sayac = self.kok.after(1000, self._geri_say)

    def alarm_dugme(self):
        if self.al_durum != 'kapali':
            self.al_ayarla('kapali', True)
            return
        self.kalan = GECIKME
        self.al_ayarla('bekliyor', False)
        self.sayac = self.kok.after(1000, self._geri_say)

    # ================================================================ Konaklama
    def konak_goster(self):
        if self.tasima:
            yazi, renk = ('MOLA' if self.mola else 'YOLDA'), (TURUNCU if self.mola else MAVI)
        elif self.kayma:
            yazi, renk = 'KONUM DEĞİŞTİ', UYARI
        elif self.konak_acik:
            yazi, renk = 'konaklama', YESIL
        else:
            yazi, renk = 'kapalı', SOLUK
        self.konak_f.renk(KAYMA_BG if self.kayma and not self.tasima else KART, None if renk == SOLUK else renk)
        self.konak_l.config(text=yazi, fg=renk, font=F(17 if yazi == 'KONUM DEĞİŞTİ' else 24, True))
        self.kb.bitti()
        self.mb.bitti()
        if self.tasima:
            self.kb.config(text='Vardık')
            self.kb.renk_ayarla(Y_YESIL)
            self.mb.config(text='Yola devam' if self.mola else 'Mola')
            self.mb.renk_ayarla(Y_MAVI if self.mola else Y_TURUNCU)
        else:
            self.kb.config(text='Konaklamayı bitir' if self.konak_acik else 'Konaklamaya hazır')
            self.kb.renk_ayarla(DUGME if self.konak_acik else Y_YESIL)
            self.mb.config(text='Yola çıkıyorum')
            self.mb.renk_ayarla(Y_MAVI)
        if self.kayma and not self.tasima:
            self.mb.place_forget()
            self.kk.place(**self.kk_yer)
        else:
            self.kk.place_forget()
            self.mb.place(**self.kk_yer)

    def konak_komut(self, on):
        self.konak_istek = on
        self.yayinla(DEV + '/switch/konaklama/command', 'ON' if on else 'OFF')

    def konak_dugme(self):
        if self.tasima:
            self.vardik(True)
            return
        if self.kb.bekle('Kapatılıyor…' if self.konak_acik else 'Açılıyor…', self.konak_goster):
            self.konak_komut(not self.konak_acik)

    # ================================================================ Taşıma modu
    def yol_dugme(self):
        if not self.tasima:
            self.kontrol_ac()
        elif self.mola:
            self.mola_bitir()
        else:
            self.mola_basla()

    def mola_basla(self):
        self.yayinla(DEV + '/switch/mola/command', 'ON')
        self.ses.soyle(['mola'], True)
        if self.al_durum == 'kapali':
            self.alarm_dugme()          # çıkış gecikmeli kur

    def mola_bitir(self):
        self.yayinla(DEV + '/switch/mola/command', 'OFF')
        if self.al_durum != 'kapali':
            self.al_ayarla('kapali', True)
        self.ses.soyle(['mola_bitti'], True)

    def vardik(self, yayin):
        """Vardık: konaklama açılır, alarm kapanır, seviye rehberi başlar."""
        if yayin:
            self.yayinla(DEV + '/switch/tasima/command', 'OFF')
            self.yayinla(DEV + '/switch/konaklama/command', 'ON')
        if self.al_durum != 'kapali':
            self.al_ayarla('kapali', True)
        self.ses.soyle(['vardik'], True)
        self.sekme('sev')
        self.kok.after(3500, lambda: self.rehber or self.rehber_ayarla(True))

    def olay(self, o):
        self.uyan()
        if o == 'salinim':
            self.sekme('genel')
            self.ses.soyle(['salinim'], True)
        elif o == 'durdu':
            self.sekme('genel')
            self.ses.soyle(['durduk'], True)
            self.durdu_soru = True
            self.sor('Durduk. Vardık mı, yoksa mola mı?\n(Telefondaki bildirimden de seçebilirsin.)',
                     lambda: self.vardik(True), evet_yazi='Vardık', hayir_yazi='Mola', hayir=self.mola_basla)
        elif o == 'tasima_oto':
            self.ses.soyle(['tasima_oto'], True)
        elif o == 'mola':
            self.ses.soyle(['mola'], True)
        elif o == 'mola_bitti':
            self.ses.soyle(['mola_bitti'], True)
        elif o == 'vardik':
            self.vardik(False)

    def konak_yeni(self):
        self.yayinla(DEV + '/switch/konaklama/command', 'OFF')
        self.kok.after(800, lambda: self.konak_komut(True))

    # ================================================================ Akü
    def aku_goster(self):
        a = self.aku

        def f(k, d, b):
            v = a.get(k)
            return '–' if v is None else ('%.' + str(d) + 'f') % v + b
        soc = a.get('aku_doluluk')
        renk = YESIL if soc is None or soc >= AKU_DUSUK else UYARI if soc >= AKU_KRITIK else KIRMIZI
        eski = time.time() - self.aku_zaman > 60
        self.soc.config(text=f('aku_doluluk', 0, ' %'), fg=ESKI if eski else renk)
        self.aku_f.serit_renk(ESKI if eski else renk)
        g = 0 if soc is None else max(0, min(100, soc)) * 3.49
        self.bar.coords(self.bar_r, *yuvarlak_noktalar(0, 0, max(g, 24), 25, 12))
        self.bar.itemconfig(self.bar_r, fill=ESKI if eski else renk, state='normal' if soc else 'hidden')
        A, kalan = a.get('aku_akim'), a.get('aku_kalan')
        kap = kalan / (soc / 100) if kalan is not None and soc else None
        self.aku_k.config(text=('%.0f / %.0f Ah' % (kalan, kap)) if kap else f('aku_kalan', 0, ' Ah'))
        s = '–'
        if A is not None and kalan is not None:
            if A < -0.3:
                s = '~%.0f sa sonra biter' % (kalan / -A)
            elif A > 0.3 and kap:
                s = '~%.1f sa sonra dolar' % ((kap - kalan) / A)
            else:
                s = 'boşta'
        self.aku_s.config(text=s)
        d = {'Idle': 'boşta', 'Charging': '⚡ şarj oluyor', 'Discharging': 'kullanılıyor', 'Offline': 'bağlantı yok',
             'Unknown': 'bilinmiyor'}.get(a.get('durum'), a.get('durum') or '')
        self.aku_dl.config(text=d, fg=YESIL if a.get('durum') == 'Charging' else SOLUK)
        self.a['v'].config(text=f('aku_voltaj', 2, ' V'), fg=ESKI if eski else YAZI)
        self.a['a'].config(text=('+' if (A or 0) > 0.05 else '') + f('aku_akim', 1, ' A'),
                           fg=ESKI if eski else YESIL if (A or 0) > 0.3 else YAZI)
        self.a['w'].config(text=f('aku_guc', 0, ' W'), fg=ESKI if eski else YAZI)
        t1, t2 = a.get('aku_sicaklik_1'), a.get('aku_sicaklik_2')
        ayri = t1 is not None and t2 is not None and round(t1) != round(t2)
        t = ('%.0f° / %.0f°' % (t1, t2)) if ayri else f('aku_sicaklik_1', 0, ' °C')
        self.a['t'].config(text=t, font=F(18 if ayri else 22, True), fg=ESKI if eski else MAVI if t1 is not None and t1 < 5 else TURUNCU if t1 is not None and t1 > 40 else YAZI)
        # hücreler: 2.9-3.6 V aralığı çubuğa yayılır
        hv = [a.get('aku_hucre_%d' % i) for i in range(1, 5)]
        dolu = [v for v in hv if v is not None]
        for (r, tx, x), v in zip(self.hucre, hv):
            if v is None:
                self.hc.itemconfig(r, state='hidden')
                self.hc.itemconfig(tx, text='–')
                continue
            oran = max(0.0, min(1.0, (v - 2.9) / 0.7))
            sapma = dolu and (v - min(dolu) > 0.05 or max(dolu) - v > 0.05)
            self.hc.coords(r, *yuvarlak_noktalar(x, 0, x + max(16, oran * 112), 26, 8))
            self.hc.itemconfig(r, state='normal', fill=ESKI if eski else UYARI if sapma else YESIL)
            self.hc.itemconfig(tx, text='%.3f V' % v, fill=ESKI if eski else YAZI)
        fark = a.get('aku_hucre_farki')
        if fark is None and len(dolu) > 1:
            fark = max(dolu) - min(dolu)
        self.hc_fark.config(text='' if fark is None else 'fark %d mV' % round(fark * 1000),
                            fg=YESIL if fark is not None and fark < 0.03 else UYARI)
        bag = 'Bluetooth bırakıldı' if not self.bms_baglanti else 'bağlı' if self.bms_bagli else 'bağlı değil'
        sat = ['Bağlantı: ' + bag]
        if self.bms_sinyal is not None:
            sat.append('Sinyal: %d dBm' % self.bms_sinyal)
        if a.get('aku_dongu') is not None:
            sat.append('Döngü: %d' % a['aku_dongu'])
        self.bms_l.config(text='\n'.join(sat), fg=YAZI if self.bms_bagli else SOLUK)
        self.oz_aku.config(text=f('aku_doluluk', 0, ' %'), fg=ESKI if eski else renk)
        self.oz_aku_c.coords(self.oz_aku_r, *self._cubuk(soc, 100))
        self.oz_aku_c.itemconfig(self.oz_aku_r, fill=renk, state='normal' if soc else 'hidden')
        self.oz_aku_a.config(text='Bluetooth bağlı değil' if soc is None else
                             f('aku_voltaj', 1, ' V') + ' · ' + f('aku_akim', 1, ' A') + ' · ' + s)
        self.bb.bitti()
        self.bb.config(text="Telefon uygulaması için Bluetooth'u bırak" if self.bms_baglanti else 'Bluetooth bağlantısını geri al')

    @staticmethod
    def _cubuk(v, tam):
        g = 0 if not v or not tam else max(0.0, min(1.0, v / tam)) * 226
        return yuvarlak_noktalar(0, 0, max(g, 12), 11, 6)

    def basinc_egilim(self, v):
        """Son 3 saatteki basınç değişimi (en az 1 saatlik kayıt varsa)."""
        simdi = time.time()
        g = self.basinc_gecmis
        if not g or simdi - g[-1][0] >= 300:
            g.append((simdi, v))
        while g and simdi - g[0][0] > 3 * 3600:
            g.pop(0)
        if not g or simdi - g[0][0] < 3600:
            self.bas_e.config(text='')
            return
        f = v - g[0][1]
        if f <= -3:
            self.bas_e.config(text='▼ hızlı düşüş', fg=TURUNCU)
        elif f <= -1:
            self.bas_e.config(text='▼ düşüyor', fg=SARI)
        elif f >= 1:
            self.bas_e.config(text='▲ yükseliyor', fg=YESIL)
        else:
            self.bas_e.config(text='► sabit', fg=SOLUK)

    def aku_ses_kontrol(self):
        d, v, simdi = self.aku.get('aku_doluluk'), self.aku.get('aku_voltaj'), time.time()
        for sv, esik in ((1, AKU_V_DUSUK), (2, AKU_V_KRITIK)):
            if v is not None and v < esik:
                self.v_alt[sv] = self.v_alt[sv] or simdi
            else:
                self.v_alt[sv] = None
        v_sev = max([sv for sv, t in self.v_alt.items() if t and simdi - t >= AKU_V_SURE] or [0])
        d_sev = 0 if d is None else 2 if d < AKU_KRITIK else 1 if d < AKU_DUSUK else 0
        sev = max(v_sev, d_sev)
        # aku_uyari: 0 normal, 1 düşük uyarısı verildi, 2 kritik uyarısı verildi
        if sev == 2 and self.aku_uyari < 2:
            self.ses.soyle(['aku_kritik'])
            self.aku_uyari = 2
        elif sev == 1 and self.aku_uyari < 1:
            self.ses.soyle(['aku_dusuk'])
            self.aku_uyari = 1
        elif sev == 0 and (d is None or d >= AKU_DUSUK + 5) and (v is None or v >= AKU_V_DUSUK + 0.2):
            self.aku_uyari = 0

    def bt_dugme(self):
        if self.bb.bekle('Bekleyin…', self.aku_goster):
            self.yayinla(AKU_DEV + '/switch/bms_baglanti/command', 'OFF' if self.bms_baglanti else 'ON')

    # ================================================================ Su
    def su_goster(self):
        l, depo = self.su.get('su_kalan'), self.su.get('su_depo_litre') or 100
        az = self.su_alt is False
        eski = time.time() - self.su_zaman > 60
        renk = ESKI if eski else TURUNCU if az else SU_MAVI
        self.sul.config(text='–' if l is None else '~%d L' % yuvarla(l), fg=ESKI if eski else UYARI if az else YAZI)
        yuzde = None if l is None else max(0, min(100, l / depo * 100))
        self.su_dl.config(text='depo %d L' % yuvarla(depo) + ('' if yuzde is None else ' · %%%d' % yuvarla(yuzde)) +
                          (' · AZALDI' if az else ''), fg=UYARI if az else SOLUK)
        self.su_f.serit_renk(renk)
        h = 0 if yuzde is None else (self.TY1 - self.TY0 - 8) * yuzde / 100
        self.tank.coords(self.tank_r, *yuvarlak_noktalar(self.TX0 + 4, self.TY1 - 4 - max(h, 28), self.TX1 - 4, self.TY1 - 4, 14))
        self.tank.itemconfig(self.tank_r, fill=renk, state='normal' if yuzde else 'hidden')
        self.tank.itemconfig(self.tank_y, text='' if yuzde is None else '%%%d' % yuvarla(yuzde))
        ak = self.su.get('su_akis')
        akiyor = ak is not None and ak > 0.05
        self.s_a.config(text='–' if ak is None else '%.1f L/dk' % ak if akiyor else 'yok', fg=SU_MAVI if akiyor else YAZI)
        g = int((time.time() * 1000 - self.su_dolum) // 86400000) if self.su_dolum else -1
        self.s_d.config(text='–' if g < 0 else 'bugün' if g == 0 else '%d gün önce' % g)
        self.s_p.config(text='–' if self.pompa is None else 'açık' if self.pompa else 'kapalı',
                        fg=YESIL if self.pompa else YAZI)
        self.s_kart['p'].serit_renk(YESIL if self.pompa else KENAR)
        self.oz_su.config(text='–' if l is None else '%d L' % yuvarla(l), fg=ESKI if eski else UYARI if az else MAVI)
        self.oz_su_c.coords(self.oz_su_r, *self._cubuk(l, depo))
        self.oz_su_c.itemconfig(self.oz_su_r, fill=TURUNCU if az else SU_MAVI, state='normal' if l else 'hidden')
        self.oz_su_a.config(text='depo %d L · pompa %s' % (yuvarla(depo), '–' if self.pompa is None else
                                                            'açık' if self.pompa else 'kapalı'))
        self.spb.bitti()
        self.spb.config(text='Pompayı kapat' if self.pompa else 'Pompayı aç')
        ls = self.su.get('su_litre_sinyal')
        self.s_k.config(text='Litre başına sinyal: %s   ·   Ölçümler: %s\nDepo %s L, sensörün altında %s L (web panelinden değiştirilir)' % (
            '–' if ls is None else yuvarla(ls), self.su_kal,
            '–' if self.su.get('su_depo_litre') is None else yuvarla(self.su['su_depo_litre']),
            '–' if self.su.get('su_sensor_alti_litre') is None else yuvarla(self.su['su_sensor_alti_litre'])))

    def gps_goster(self):
        g = self.gps
        fix = g.get('gps_enlem') is not None and g.get('gps_boylam') is not None
        u = g.get('gps_uydu')
        uydu = '–' if u is None else '%d uydu' % yuvarla(u)
        eski = time.time() - self.gps_zaman > 60
        r, h = g.get('gps_rakim'), g.get('gps_hiz')
        if fix:
            self.g_l.config(text='%.5f, %.5f' % (g['gps_enlem'], g['gps_boylam']), fg=ESKI if eski else YAZI)
            ek = [uydu]
            if r is not None:
                ek.append('%d m' % yuvarla(r))
            if h is not None:
                ek.append('%d km/h' % yuvarla(h))
            self.g_k.config(text=' · '.join(ek))
        else:
            self.g_l.config(text='aranıyor…', fg=ESKI if eski else YAZI)
            self.g_k.config(text=uydu + ' görülüyor' if u else 'uydu bekleniyor')

    def depo_dolu(self):
        def evet():
            self.yayinla(DEV + '/button/su_depo_dolu/command', 'PRESS')
            self.yayinla(SU_TOPIC, str(int(time.time() * 1000)), True)
            self.ses.soyle(['su_dolu'], True)
        self.sor('Depo şu an tam dolu mu?\n(Tam dolu değilse kalibrasyon yanlış öğrenir.)', evet)

    def pompa_dugme(self):
        if self.spb.bekle('Kapatılıyor…' if self.pompa else 'Açılıyor…', self.su_goster):
            self.yayinla(DEV + '/switch/su_pompasi/command', 'OFF' if self.pompa else 'ON')

    def kal_sifirla(self):
        self.sor('Kalibrasyon kaydı silinsin ve katalog değerine (450) dönülsün mü?',
                 lambda: self.yayinla(DEV + '/button/su_kalibrasyon_sifirla/command', 'PRESS'))

    # ================================================================ Seviye
    def koseler(self):
        tp, tr = math.tan(math.radians(self.egim_on)), math.tan(math.radians(self.egim_yan))
        L, W = self.ayar['boy'] / 2, self.ayar['en'] / 2
        z = {'sol_on': L * tp - W * tr, 'sag_on': L * tp + W * tr, 'sol_arka': -L * tp - W * tr, 'sag_arka': -L * tp + W * tr}
        ust, r = max(z.values()), {}
        for k, v in z.items():
            # "indir" = ayağı uzat, köşe yükselir. "kaldır" = ayağı topla, köşe alçalır.
            fark = ust - v if self.ayar.get('yontem') == 'indir' else -v
            r[k] = {'k': k, 'is': 'indir' if fark > 0 else 'kaldir', 'cm': abs(fark)}
        return r

    def en_iyi(self, r):
        l = [x for x in r.values() if x['cm'] >= ESIK_CM]
        if not l:
            return None
        l.sort(key=lambda x: (-x['cm'], 0 if x['is'] == 'indir' else 1))   # eşitlikte önce indir
        h = self.hedef
        # Aynı köşe hâlâ ayar istiyorsa ve fark küçükse hedefi değiştirme (zıplamasın)
        if h and r[h['k']]['cm'] >= ESIK_CM and r[h['k']]['is'] == h['is'] and l[0]['cm'] - r[h['k']]['cm'] < 1:
            return r[h['k']]
        return l[0]

    @staticmethod
    def cm_ses(cm):
        c = yuvarla(cm)
        return 'cm_az' if c < 1 else 'cm_cok' if c > 20 else 'cm_%d' % c

    def seviye_goster(self):
        if self.egim_on is None or self.egim_yan is None:
            return
        # karekök ölçek: merkeze yakın hassas; halkalar 22 px ≈ 0,6°, 44 px ≈ 2,5°, kenar 5°+
        m = math.hypot(self.egim_yan, self.egim_on)
        k = 0 if m < 1e-6 else 58 * math.sqrt(min(m, 5) / 5) / m
        x, y = self.bx + self.egim_yan * k, self.by - self.egim_on * k
        r = self.koseler()
        t = self.en_iyi(r)
        rk = TURUNCU if t else YESIL
        self.sev_c.coords(self.dot, x - 11, y - 11, x + 11, y + 11)
        self.sev_c.coords(self.dot_g, x - 15, y - 15, x + 15, y + 15)
        self.sev_c.coords(self.dot_p, x - 6, y - 7, x - 1, y - 3)
        self.sev_c.itemconfig(self.dot, fill=rk)
        self.sev_c.itemconfig(self.dot_g, outline=rk)
        self.nabiz_k = t['k'] if t else None
        self.tal_f.serit_renk(TURUNCU if t else YESIL)
        for k, x_ in r.items():
            kutu, yazi = self.kose[k]
            ayar_ister = x_['cm'] >= ESIK_CM
            zemin = ('#3a2412' if x_['is'] == 'indir' else '#122a40') if ayar_ister else '#12301d'
            self.sev_c.itemconfig(kutu, fill=zemin, outline=SARI if (t and t['k'] == k) else zemin)
            self.sev_c.itemconfig(yazi, fill=(TURUNCU if x_['is'] == 'indir' else MAVI) if ayar_ister else YESIL,
                                  text=('↓ ' if x_['is'] == 'indir' else '↑ ') + '%d cm' % yuvarla(x_['cm']) if ayar_ister else '✓')
        adlar = {'sol_on': 'Sol ön', 'sag_on': 'Sağ ön', 'sol_arka': 'Sol arka', 'sag_arka': 'Sağ arka'}
        eski = time.time() - self.egim_zaman > 10
        self.talimat.config(text=(adlar[t['k']] + ' ayağı ' + ('indir' if t['is'] == 'indir' else 'kaldır') +
                                  ', ~%d cm' % yuvarla(t['cm'])) if t else 'Karavan düz ✓',
                            fg=ESKI if eski else YAZI if t else YESIL)

        def yz(v, a, b):
            return ('+' if v >= 0 else '') + '%.1f° ' % v + ('' if abs(v) < 0.1 else a if v > 0 else b)
        self.egimler.config(text='Ön-arka: ' + yz(self.egim_on, '(ön yüksek)', '(arka yüksek)') +
                            '  ·  Sol-sağ: ' + yz(self.egim_yan, '(sağ yüksek)', '(sol yüksek)'))

    def _sev_nabiz(self):
        """Sıradaki ayağın kutusu yanıp söner."""
        self.nabiz = not self.nabiz
        for k, (kutu, _) in self.kose.items():
            if k == self.nabiz_k:
                self.sev_c.itemconfig(kutu, outline=SARI if self.nabiz else '#7a5a10', width=4 if self.nabiz else 3)
        self.kok.after(600, self._sev_nabiz)

    def ayar_goster(self):
        self.yb.config(text='Yöntem: ' + ('sadece indir (en yüksek köşeye göre)' if self.ayar.get('yontem') == 'indir'
                                          else 'indir ve kaldır (yükseklik aynı kalır)'))
        self.olcu.config(text='↓ indir  ·  ↑ kaldır  ·  ✓ tamam\nAyaklar arası: ön-arka %s cm, sol-sağ %s cm (web panelinden)' %
                         (self.ayar.get('boy'), self.ayar.get('en')))

    def yontem_dugme(self):
        self.ayar['yontem'] = 'orta' if self.ayar.get('yontem') == 'indir' else 'indir'
        self.yayinla(AYAR_TOPIC, json.dumps(self.ayar), True)
        self.ayar_goster()
        self.seviye_goster()

    def duz_kabul(self):
        def evet():
            self.yayinla(DEV + '/button/duz_kabul_et/command', 'PRESS')
            self.ses.soyle(['duz_kabul'], True)
        self.sor('Karavan şu an gerçekten düz mü? (Bir su terazisiyle kontrol et.)\n'
                 'Bu konum sıfır noktası olarak kaydedilecek.', evet)

    def rehber_ayarla(self, a):
        self.rehber, self.hedef, self.duz_say, self.son_ses = a, None, 0, 0
        self.rb.config(text='Sesli seviye ayarını durdur' if a else 'Sesli seviye ayarını başlat')
        self.rb.renk_ayarla(DUGME if a else SECILI)
        if a:
            self.ses.soyle(['basla'], True)
        else:
            self.ses.bosalt()

    def _rehber_adim(self):
        if not self.rehber:
            return
        simdi = time.time()
        if simdi - self.egim_zaman > 5 or self.egim_on is None or self.egim_yan is None:
            if simdi - self.veri_yok_ses > 15:
                self.ses.soyle(['veri_yok'], True)
                self.veri_yok_ses = simdi
            return
        t = self.en_iyi(self.koseler())
        if not t:
            self.duz_say += 1
            if self.duz_say >= 3:
                self.rehber_ayarla(False)
                self.ses.soyle(['duz'], True)
            return
        self.duz_say = 0
        h = self.hedef
        if not h or h['k'] != t['k'] or h['is'] != t['is']:
            self.ses.soyle((['tamam'] if h else []) + [t['k'] + '_' + t['is'] + self.cm_ses(t['cm'])[2:]], bool(h))   # tek cümle: sol_arka_indir_5
            self.hedef, self.son_ses = t, simdi
        elif simdi - self.son_ses > 8 and not self.ses.konusuyor():
            self.ses.soyle([self.cm_ses(t['cm'])])
            self.son_ses = simdi

    # ================================================================ Zamanlayıcılar
    def _saniyede(self):
        try:
            self.saat.config(text=time.strftime('%H:%M'))
            self._rehber_adim()
        finally:
            self.kok.after(1000, self._saniyede)

    def _bes_saniyede(self):
        try:
            simdi = time.time()
            if self.kayma and simdi - self.kayma_ses > 300:
                self.ses.soyle(['kayma'])
                self.kayma_ses = simdi
            for k, z in self.seen.items():
                if simdi - z > 120:
                    self.d[k].config(fg=ESKI)
            self.aku_goster()
            self.su_goster()
            self.gps_goster()
            self.seviye_goster()
        finally:
            self.kok.after(5000, self._bes_saniyede)

    def _otuz_saniyede(self):
        # 5 dakika dokunulmazsa Genel'e dön
        if self.aktif != 'genel' and time.time() - self.sekme_zaman > 300:
            self.sekme('genel')
        if time.time() - self.son_dokunus > KARART_SN and self.al_durum != 'caliyor' and not self.rehber:
            self.karart()
        self.kok.after(30000, self._otuz_saniyede)


def main():
    kok = tk.Tk()
    kok.title('Karavan')
    if os.environ.get('KARAVAN_PENCERE') != '1':
        # Kiosk: ekranı kapla, çerçeve yok, imleç yok
        kok.overrideredirect(True)
        kok.geometry('%dx%d+0+0' % (kok.winfo_screenwidth(), kok.winfo_screenheight()))
        kok.config(cursor='none')
    else:
        kok.geometry('800x480')
    Panel(kok)
    threading.Thread(target=siren_dosyasi, daemon=True).start()   # sireni önceden hazırla
    kok.mainloop()


if __name__ == '__main__':
    main()
