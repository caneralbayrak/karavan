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
AL_TOPIC = 'karavan/alarm'
AYAR_TOPIC = 'karavan/ayar'
SU_TOPIC = 'karavan/su_doldurma'
BURASI = os.path.dirname(os.path.abspath(__file__))
SES_DIR = os.path.join(BURASI, '..', 'panel', 'sesler')
SIREN = os.path.expanduser('~/.cache/karavan-siren.wav')

GECIKME = 30        # alarm kurulduktan sonra dışarı çıkmak için saniye
ESIK_CM = 1         # bundan az fark varsa köşe düz sayılır
AKU_DUSUK, AKU_KRITIK = 20, 10
KARART_SN = 300    # 5 dk dokunulmazsa ekran kararır (akü tasarrufu)

# Renkler (web paneliyle aynı)
BG, KART, KENAR, YAZI, SOLUK, ESKI = '#0d1117', '#161b22', '#2a3340', '#e8edf3', '#8b96a5', '#4a5360'
YESIL, TURUNCU, MAVI, SARI, MOR = '#56d364', '#f0883e', '#79c0ff', '#e3b341', '#d2a8ff'
KIRMIZI, UYARI, SU_MAVI = '#ff7b72', '#f0b33a', '#388bfd'
DUGME, DUGME_BAS, BEKLE, SECILI = '#262e3a', '#3a4556', '#2a4a6a', '#1f6feb'
KIRMIZI_DUGME, YESIL_DUGME = '#b62324', '#1a7f37'
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
        super().__init__(ust, text=yazi, bg=renk, fg=YAZI, font=F(boy), **kw)
        self.komut, self.renk = komut, renk
        self.bekliyor, self._z = False, None
        Dugme.hepsi.append(self)
        self.bind('<ButtonPress-1>', self._bas)
        self.bind('<ButtonRelease-1>', self._birak)

    def renk_ayarla(self, r):
        self.renk = r
        if not self.bekliyor:
            self.config(bg=r)

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
        self.config(bg=BEKLE, text=yazi)
        self._z = self.after(5000, lambda: (self.bitti(), geri_al()))
        return True

    def bitti(self):
        if self._z:
            self.after_cancel(self._z)
            self._z = None
        if self.bekliyor:
            self.bekliyor = False
            self.config(bg=self.renk)


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
        self.aku, self.aku_zaman, self.aku_uyari = {}, 0, 0
        self.bms_bagli, self.bms_baglanti = False, True
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

    def sor(self, metin, evet):
        self.sor_evet = evet
        self.sor_m.config(text=metin)
        self.sor_f.place(x=0, y=0, width=800, height=480)
        self.sor_f.tkraise()

    def _onay_kutusu(self):
        self.sor_evet = None
        f = tk.Frame(self.kok, bg='#080808')
        k = tk.Frame(f, bg=KART, highlightthickness=1, highlightbackground=KENAR)
        k.place(x=130, y=130, width=540, height=200)
        self.sor_m = tk.Label(k, text='', bg=KART, fg=YAZI, font=F(15), wraplength=500, justify='left')
        self.sor_m.place(x=18, y=14)

        def kapat(evet):
            f.place_forget()
            fn, self.sor_evet = self.sor_evet, None
            if evet and fn:
                fn()
        Dugme(k, 'Vazgeç', lambda: kapat(False), boy=16).place(x=18, y=118, width=240, height=62)
        Dugme(k, 'Evet', lambda: kapat(True), boy=16, renk=YESIL_DUGME).place(x=280, y=118, width=240, height=62)
        self.sor_f = f

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
        self.ab = Dugme(self.al_f, 'Alarmı kur', self.alarm_dugme, boy=15, renk=KIRMIZI_DUGME)
        self.ab.place(x=14, y=144, width=227, height=54)
        self.konak_f, _ = kart(s, 534, 106, 258, 212, 'Konaklama', 'konak')
        self.konak_l = deger(self.konak_f, 14, 44, boy=26)
        self.kb = Dugme(self.konak_f, 'Konaklamaya hazır', self.konak_dugme, boy=15, renk=YESIL_DUGME)
        self.kb.place(x=14, y=144, width=230, height=54)
        self.kk = Dugme(self.konak_f, 'Kontrol ettim, yeni\nkonumu kaydet', self.konak_yeni, boy=13)
        self.kk_yer = dict(x=14, y=88, width=230, height=50)
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
        f, self.aku_b = kart(s, 8, 6, 784, 260, 'Akü')
        self.soc = deger(f, 14, 30, boy=32)
        self.bar = tk.Canvas(f, width=160, height=14, bg='#26303c', highlightthickness=0)
        self.bar.place(x=16, y=100)
        self.bar_r = self.bar.create_rectangle(0, 0, 0, 14, fill=YESIL, width=0)
        self.a = {}
        alanlar = (('v', 'Voltaj'), ('a', 'Akım'), ('w', 'Güç'), ('k', 'Kalan'),
                   ('s', 'Süre'), ('h', 'Hücreler'), ('t', 'Sıcaklık'), ('d', 'Durum'))
        for i, (k, bas) in enumerate(alanlar):
            self.a[k] = kucuk_bilgi(f, 200 + (i % 4) * 145, 24 + (i // 4) * 62, bas, w=140)
        self.bb = Dugme(f, "Telefon uygulaması için Bluetooth'u bırak", self.bt_dugme)
        self.bb.place(x=200, y=160, width=570, height=50)

    # ---------------- Su
    def _su(self, s):
        self.su_f, _ = kart(s, 8, 6, 784, 330, 'Temiz su')
        f = self.su_f
        self.tank = tk.Canvas(f, width=74, height=114, bg=KART, highlightthickness=0)
        self.tank.place(x=14, y=30)
        self.tank.create_rectangle(1, 1, 73, 113, outline='#3a4556', width=2)
        self.tank_r = self.tank.create_rectangle(3, 112, 71, 112, fill=SU_MAVI, width=0)
        self.sul = deger(f, 110, 26, boy=28)
        self.s_a = kucuk_bilgi(f, 110, 86, 'Akış')
        self.s_d = kucuk_bilgi(f, 260, 86, 'Dolduruldu')
        self.s_p = kucuk_bilgi(f, 410, 86, 'Pompa')
        self.sdb = Dugme(f, 'Depoyu doldurdum', self.depo_dolu)
        self.sdb.place(x=110, y=150, width=325, height=52)
        self.spb = Dugme(f, 'Pompayı aç', self.pompa_dugme)
        self.spb.place(x=445, y=150, width=325, height=52)
        self.s_k = tk.Label(f, text='', bg=KART, fg=SOLUK, font=F(11), anchor='w', justify='left', wraplength=660)
        self.s_k.place(x=110, y=212)
        Dugme(f, 'Kalibrasyon kaydını sıfırla', self.kal_sifirla, boy=13).place(x=110, y=266, width=325, height=46)

    # ---------------- Seviye
    def _seviye(self, s):
        f, _ = kart(s, 8, 4, 784, 408, 'Seviye')
        self.sev_f = f
        c = tk.Canvas(f, width=236, height=370, bg=KART, highlightthickness=0)
        c.place(x=8, y=30)
        c.create_text(118, 8, text='ÖN', fill=SOLUK, font=F(10))
        c.create_rectangle(8, 20, 228, 362, outline='#3a4556', width=2)
        self.kose = {}
        yer = {'sol_on': (14, 26), 'sag_on': (136, 26), 'sol_arka': (14, 302), 'sag_arka': (136, 302)}
        adlar = {'sol_on': 'Sol ön', 'sag_on': 'Sağ ön', 'sol_arka': 'Sol arka', 'sag_arka': 'Sağ arka'}
        for k, (x, y) in yer.items():
            r = c.create_rectangle(x, y, x + 86, y + 54, fill='#222a35', outline='#222a35', width=3)
            c.create_text(x + 43, y + 13, text=adlar[k], fill='#aaa', font=F(10))
            t = c.create_text(x + 43, y + 36, text='–', fill=YESIL, font=F(12, True))
            self.kose[k] = (r, t)
        self.bx, self.by = 118, 191
        c.create_oval(self.bx - 55, self.by - 55, self.bx + 55, self.by + 55, outline='#3a4556', width=2)
        self.dot = c.create_oval(self.bx - 9, self.by - 9, self.bx + 9, self.by + 9, fill=YESIL, width=0)
        self.sev_c = c
        self.talimat = tk.Label(f, text='–', bg=KART, fg=YAZI, font=F(16, True), anchor='w', justify='left', wraplength=520)
        self.talimat.place(x=258, y=30)
        self.egimler = tk.Label(f, text='', bg=KART, fg=SOLUK, font=F(12), anchor='w', justify='left', wraplength=520)
        self.egimler.place(x=258, y=100)
        self.rb = Dugme(f, 'Sesli seviye ayarını başlat', lambda: self.rehber_ayarla(not self.rehber))
        self.rb.place(x=258, y=150, width=514, height=54)
        self.yb = Dugme(f, '', self.yontem_dugme, boy=14)
        self.yb.place(x=258, y=214, width=514, height=48)
        self.dk = Dugme(f, 'Bu konumu düz kabul et (sıfırla)', self.duz_kabul, boy=14)
        self.dk.place(x=258, y=272, width=514, height=48)
        self.olcu = tk.Label(f, text='', bg=KART, fg=SOLUK, font=F(10), anchor='w', justify='left', wraplength=514)
        self.olcu.place(x=258, y=330)
        self.ayar_goster()

    # ================================================================ MQTT
    def _baglandi(self, c, u, flags, rc, props=None):
        if rc != 0:
            return
        for t in (AL_TOPIC, AYAR_TOPIC, SU_TOPIC, DEV + '/sensor/+/state', DEV + '/binary_sensor/+/state',
                  DEV + '/switch/+/state', DEV + '/text_sensor/su_kalibrasyon/state', DEV + '/number/+/state'):
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
                if ad == 'aku_doluluk':
                    self.aku_ses_kontrol()
            else:
                return
            self.aku_goster()
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
        self.ab.renk_ayarla(KIRMIZI_DUGME if self.al_durum == 'kapali' else DUGME)
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
        self.konak_f.renk(KAYMA_BG if self.kayma else KART,
                          UYARI if self.kayma else YESIL if self.konak_acik else None)
        self.konak_l.config(text='KONUM DEĞİŞTİ' if self.kayma else 'izleniyor' if self.konak_acik else 'kapalı',
                            fg=UYARI if self.kayma else YESIL if self.konak_acik else SOLUK,
                            font=F(17 if self.kayma else 26, True))
        self.kb.bitti()
        self.kb.config(text='Konaklamayı bitir' if self.konak_acik else 'Konaklamaya hazır')
        self.kb.renk_ayarla(DUGME if self.konak_acik else YESIL_DUGME)
        if self.kayma:
            self.kk.place(**self.kk_yer)
        else:
            self.kk.place_forget()

    def konak_komut(self, on):
        self.konak_istek = on
        self.yayinla(DEV + '/switch/konaklama/command', 'ON' if on else 'OFF')

    def konak_dugme(self):
        if self.kb.bekle('Kapatılıyor…' if self.konak_acik else 'Açılıyor…', self.konak_goster):
            self.konak_komut(not self.konak_acik)

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
        self.soc.config(text=f('aku_doluluk', 0, ' %'), fg=ESKI if eski else (YAZI if renk == YESIL else renk))
        self.bar.coords(self.bar_r, 0, 0, 1.6 * max(0, min(100, soc or 0)), 14)
        self.bar.itemconfig(self.bar_r, fill=renk)
        self.a['v'].config(text=f('aku_voltaj', 2, ' V'))
        self.a['a'].config(text=f('aku_akim', 1, ' A'))
        self.a['w'].config(text=f('aku_guc', 0, ' W'))
        self.a['k'].config(text=f('aku_kalan', 0, ' Ah'))
        A, kalan = a.get('aku_akim'), a.get('aku_kalan')
        s = '–'
        if A is not None and kalan is not None:
            kap = kalan / (soc / 100) if soc else 0
            if A < -0.3:
                s = '~%.0f sa (bitiş)' % (kalan / -A)
            elif A > 0.3 and kap > 0:
                s = '~%.1f sa (dolum)' % ((kap - kalan) / A)
            else:
                s = 'boşta'
        self.a['s'].config(text=s)
        self.a['h'].config(text=f('aku_min_hucre', 3, '') + ' – ' + f('aku_max_hucre', 3, ' V'))
        t = f('aku_sicaklik_1', 0, ' °C') + (' / ' + f('aku_sicaklik_2', 0, ' °C') if 'aku_sicaklik_2' in a else '')
        self.a['t'].config(text=t)
        d = {'Idle': 'boşta', 'Charging': 'şarj oluyor', 'Discharging': 'kullanılıyor', 'Offline': 'bağlantı yok',
             'Unknown': 'bilinmiyor'}.get(a.get('durum'), a.get('durum') or '–')
        if a.get('hatalar') and a.get('hatalar') != 'Offline':
            d += ' ⚠ ' + a['hatalar']
        self.a['d'].config(text=d)
        self.oz_aku.config(text=f('aku_doluluk', 0, ' %'), fg=ESKI if eski else renk)
        self.oz_aku_c.coords(self.oz_aku_r, *self._cubuk(soc, 100))
        self.oz_aku_c.itemconfig(self.oz_aku_r, fill=renk, state='normal' if soc else 'hidden')
        self.oz_aku_a.config(text='Bluetooth bağlı değil' if soc is None else
                             f('aku_voltaj', 1, ' V') + ' · ' + f('aku_akim', 1, ' A') + ' · ' + s)
        ek = '(Bluetooth bırakıldı)' if not self.bms_baglanti else '' if self.bms_bagli else '(bağlı değil)'
        self.aku_b.config(text='Akü ' + ek)
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
        d = self.aku.get('aku_doluluk')
        if d is None:
            return
        # 0 normal, 1 düşük uyarısı verildi, 2 kritik uyarısı verildi (25 üstüne çıkınca sıfırlanır)
        if d < AKU_KRITIK and self.aku_uyari < 2:
            self.ses.soyle(['aku_kritik'])
            self.aku_uyari = 2
        elif d < AKU_DUSUK and self.aku_uyari < 1:
            self.ses.soyle(['aku_dusuk'])
            self.aku_uyari = 1
        elif d >= AKU_DUSUK + 5:
            self.aku_uyari = 0

    def bt_dugme(self):
        if self.bb.bekle('Bekleyin…', self.aku_goster):
            self.yayinla(DEV + '/switch/bms_baglanti/command', 'OFF' if self.bms_baglanti else 'ON')

    # ================================================================ Su
    def su_goster(self):
        l, depo = self.su.get('su_kalan'), self.su.get('su_depo_litre') or 100
        az = self.su_alt is False
        eski = time.time() - self.su_zaman > 60
        self.sul.config(text='–' if l is None else '~%d L' % yuvarla(l),
                        fg=ESKI if eski else UYARI if az else YAZI)
        h = 0 if l is None else min(100, l / depo * 100) * 1.09
        self.tank.coords(self.tank_r, 3, 112 - h, 71, 112)
        self.tank.itemconfig(self.tank_r, fill=TURUNCU if az else SU_MAVI)
        ak = self.su.get('su_akis')
        self.s_a.config(text='–' if ak is None else '%.1f L/dk' % ak if ak > 0.05 else 'yok')
        g = int((time.time() * 1000 - self.su_dolum) // 86400000) if self.su_dolum else -1
        self.s_d.config(text='–' if g < 0 else 'bugün' if g == 0 else '%d gün önce' % g)
        self.s_p.config(text='–' if self.pompa is None else 'açık' if self.pompa else 'kapalı')
        self.oz_su.config(text='–' if l is None else '%d L' % yuvarla(l), fg=ESKI if eski else UYARI if az else MAVI)
        self.oz_su_c.coords(self.oz_su_r, *self._cubuk(l, depo))
        self.oz_su_c.itemconfig(self.oz_su_r, fill=TURUNCU if az else SU_MAVI, state='normal' if l else 'hidden')
        self.oz_su_a.config(text='depo %d L · pompa %s' % (yuvarla(depo), '–' if self.pompa is None else
                                                            'açık' if self.pompa else 'kapalı'))
        self.spb.bitti()
        self.spb.config(text='Pompayı kapat' if self.pompa else 'Pompayı aç')
        ls = self.su.get('su_litre_sinyal')
        self.s_k.config(text='Litre başına sinyal: %s   ·   Ölçüm kaydı: %s\nDepo: %s L, sensörün altında: %s L (web panelinden değiştirilir)' % (
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
        def c(v):
            return max(-5, min(5, v)) * 9
        x, y = self.bx + c(self.egim_yan), self.by - c(self.egim_on)
        r = self.koseler()
        t = self.en_iyi(r)
        self.sev_c.coords(self.dot, x - 9, y - 9, x + 9, y + 9)
        self.sev_c.itemconfig(self.dot, fill=TURUNCU if t else YESIL)
        for k, x_ in r.items():
            kutu, yazi = self.kose[k]
            ayar_ister = x_['cm'] >= ESIK_CM
            self.sev_c.itemconfig(kutu, outline=SARI if (t and t['k'] == k) else '#222a35')
            self.sev_c.itemconfig(yazi, fill=(TURUNCU if x_['is'] == 'indir' else MAVI) if ayar_ister else YESIL,
                                  text=('indir ' if x_['is'] == 'indir' else 'kaldır ') + '%d cm' % yuvarla(x_['cm']) if ayar_ister else '✓')
        adlar = {'sol_on': 'Sol ön', 'sag_on': 'Sağ ön', 'sol_arka': 'Sol arka', 'sag_arka': 'Sağ arka'}
        eski = time.time() - self.egim_zaman > 10
        self.talimat.config(text=(adlar[t['k']] + ' ayağı ' + ('indir' if t['is'] == 'indir' else 'kaldır') +
                                  ', ~%d cm' % yuvarla(t['cm'])) if t else 'Karavan düz ✓', fg=ESKI if eski else YAZI)

        def yz(v, a, b):
            return ('+' if v >= 0 else '') + '%.1f° ' % v + ('' if abs(v) < 0.1 else a if v > 0 else b)
        self.egimler.config(text='Ön-arka: ' + yz(self.egim_on, '(ön yüksek)', '(arka yüksek)') +
                            '  ·  Sol-sağ: ' + yz(self.egim_yan, '(sağ yüksek)', '(sol yüksek)'))

    def ayar_goster(self):
        self.yb.config(text='Yöntem: ' + ('sadece indir (en yüksek köşeye göre)' if self.ayar.get('yontem') == 'indir'
                                          else 'indir ve kaldır (yükseklik aynı kalır)'))
        self.olcu.config(text='Ayaklar arası: ön-arka %s cm, sol-sağ %s cm (web panelinden değiştirilir)' %
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
            self.ses.soyle((['tamam'] if h else []) + [t['k'] + '_' + t['is'], self.cm_ses(t['cm'])], bool(h))
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
