#!/usr/bin/env python3
# Karavan genel bağlantı şeması v2 (ESP1 + ESP3, LiYCY damar renkleri) -> A4 yatay
W, H = 2970, 2100
o = []
def t(x, y, s, size=28, w="normal", a="start", c="#000"):
    o.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" text-anchor="{a}" fill="{c}">{s}</text>')
def r(x, y, w, h, fill="#fff", st="#000", sw=4, rx=14):
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{st}" stroke-width="{sw}"/>')
def l(pts, c="#000", sw=7):
    p = " ".join(f"{a},{b}" for a, b in pts)
    if c in ("#ffffff",):
        o.append(f'<polyline points="{p}" fill="none" stroke="#777" stroke-width="{sw+5}" stroke-linejoin="round"/>')
    o.append(f'<polyline points="{p}" fill="none" stroke="{c}" stroke-width="{sw}" stroke-linejoin="round"/>')
def dot(x, y): o.append(f'<circle cx="{x}" cy="{y}" r="11" fill="#000"/>')
def res_h(x, y, lab):
    r(x-55, y-20, 110, 40, "#fff", "#000", 4, 4); t(x, y-30, lab, 26, "bold", "middle")
def res_v(x, y, lab, side=1, h=80):
    r(x-18, y-h/2, 36, h, "#fff", "#000", 4, 4); t(x+side*30, y+9, lab, 25, "bold", "start" if side > 0 else "end")
def gnd(x, y, up=False):
    for i, w in enumerate((40, 26, 12)):
        yy = y - i*10 if up else y + i*10
        o.append(f'<line x1="{x-w}" y1="{yy}" x2="{x+w}" y2="{yy}" stroke="#000" stroke-width="5"/>')
def pill(x, y, kind):
    col, lab = {"5": ("#e00000", "5V"), "3": ("#f08000", "3.3V"), "g": ("#000", "GND")}[kind]
    r(x, y-21, 88, 38, col, col, 2, 19); t(x+44, y+8, lab, 24, "bold", "middle", "#fff")
D = {"kırmızı": "#e00000", "mavi": "#1a5fd0", "gri": "#8a8a8a", "pembe": "#ff6fb0", "beyaz": "#ffffff",
     "kahve": "#8b4513", "yeşil": "#21a336", "sarı": "#f2c500"}
def sw(x, y, d):
    o.append(f'<circle cx="{x}" cy="{y}" r="15" fill="{D[d]}" stroke="#444" stroke-width="3"/>')

o.append(f'<rect width="{W}" height="{H}" fill="#fff"/>')
t(W/2, 80, "Akıllı Karavan – ESP32 #1 bağlantı şeması (kablolama)", 52, "bold", "middle")
t(W/2, 128, "Kablo: ERSE LiYCY 8×0,22 • renkler damar renkleri • GND hepsinde ORTAK • 2026-11-15", 28, "normal", "middle", "#444")

# besleme zinciri
py = 225; bx = 870
for i, (a, b, f) in enumerate([("12V Akü", "sigorta panosu", "#ffe9a8"), ("Sigorta", "3 A", "#fff"), ("DC-DC", "12V → 5V", "#e8f4ff")]):
    r(bx, py-55, 300, 115, f); t(bx+150, py-8, a, 31, "bold", "middle"); t(bx+150, py+36, b, 25, "normal", "middle")
    if i < 2: l([(bx+300, py), (bx+370, py)], "#e00000", 9)
    bx += 370
ex0, ex1, ey0, ey1 = 1230, 1740, 420, 1730
l([(bx-70, py), (bx+60, py), (bx+60, 340), (1330, 340), (1330, ey0)], "#e00000", 9)
t(bx+80, py+10, "5V hattı", 30, "bold", "start", "#e00000")
r(ex0, ey0, ex1-ex0, ey1-ey0, "#dde8ff", "#000", 6, 26)
for x, lab, c in ((1330, "VIN", "#e00000"), (1485, "GND", "#000"), (1640, "3V3", "#f08000")):
    t(x, ey0+48, lab, 30, "bold", "middle", c)
l([(1485, ey0), (1485, 365)], "#000", 9); t(1500, 388, "ortak GND", 24)
l([(1640, ey0), (1640, 365), (1900, 365)], "#f08000", 9); t(1910, 375, "3.3V hattı", 28, "bold", "start", "#f08000")
t(1485, 1215, "ESP32 #1", 52, "bold", "middle"); t(1485, 1265, "sensor-dugumu", 32, "normal", "middle")
t(1485, 1305, "akünün yanında, plakette", 25, "normal", "middle", "#444")

ROW = 46
def device(x, y, w, title, sub, rows, side):
    """rows: (damar|None, etiket, tür)  tür: '5','3','g' ya da ('s', gpio)"""
    subs = sub.split("|") if sub else []
    h = 88 + len(rows)*ROW + 30*len(subs)
    r(x, y, w, h, "#f2f2f2"); t(x+w/2, y+40, title, 30, "bold", "middle")
    for i, s in enumerate(subs): t(x+w/2, y+74+i*30, s, 22, "normal", "middle", "#333")
    yy = y + 42 + 30*len(subs); pos = {}
    for i, (d, lab, k) in enumerate(rows):
        p = yy + 56 + i*ROW
        if side == "L":
            tx = x+22
            if d: sw(x+34, p, d); tx = x+60
            t(tx, p+9, lab, 26, "bold")
            if isinstance(k, tuple): pos[k[1]] = (x+w, p, D.get(d, "#000"))
            else: pill(x+w-104, p, k)
        else:
            tx = x+w-22
            if d: sw(x+w-34, p, d); tx = x+w-60
            t(tx, p+9, lab, 26, "bold", "end")
            if isinstance(k, tuple): pos[k[1]] = (x, p, D.get(d, "#000"))
            else: pill(x+16, p, k)
    return pos, y+h
def esp_pin(g, y, side, c="#000"):
    if side == "L": t(ex0+18, y+10, f"GPIO{g}", 28, "bold"); return ex0
    t(ex1-18, y+10, f"GPIO{g}", 28, "bold", "end"); return ex1
def wire_L(pos, g, y_=None):
    xx, yy, c = pos[g]; e = esp_pin(g, yy, "L"); l([(xx, yy), (e, yy)], c); return yy

# ---------- SOL: kablolu hatlar ----------
LX, LW = 50, 640
y = 430
pp, y = device(LX, y, LW, "Pompa / depo – tek kablo, 2,5 m", "tekli 5V röle (COM–NO → pompa +)|akış, XKC, su DS18B20",
    [("kırmızı", "5V (hepsi)", "5"), ("mavi", "GND (hepsi)", "g"), ("pembe", "3.3V (DS18B20)", "3"),
     ("yeşil", "XKC sarı tel", ("s", "32")), ("beyaz", "Röle IN", ("s", "25")),
     ("sarı", "Su DS18B20 data", ("s", "4")), ("kahve", "Akış sarı tel", ("s", "33"))], "L")
yy = wire_L(pp, "32"); nx = 900; dot(nx, yy); l([(nx, yy), (nx, yy-150)], "#000", 5); res_v(nx, yy-75, "20k+10k", 1, 90); gnd(nx, yy-150, True)
wire_L(pp, "25"); wire_L(pp, "4")
yy = wire_L(pp, "33"); nx = 1080; dot(nx, yy); l([(nx, yy), (nx, yy+105)], "#000", 5); res_v(nx, yy+52, "20k", 1); gnd(nx, yy+105)
y += 18
for g, ttl, sub in (("34", "MQ-7 (CO) – kablo 1,5 m", "yatak yanı duvar, yatarken baş hizası +30-50 cm"),
                    ("35", "MQ-6 (LPG) ocak altı – 1 m", "yerden 10-30 cm • DO boş"),
                    ("36", "MQ-6 (LPG) şofben altı – 4 m", "sensör sonra gelecek; kabloyu şimdi çek")):
    mq, y2 = device(LX, y, LW, ttl, sub, [("kırmızı", "VCC", "5"), ("mavi", "GND  (+ gri)", "g"), ("beyaz", "AO", ("s", g))], "L")
    yy = wire_L(mq, g); res_h(800, yy, "10k")
    nx = 1010; dot(nx, yy); l([(nx, yy), (nx, yy+82)], "#000", 5); res_v(nx, yy+42, "20k", 1, 56); gnd(nx, yy+82)
    y = y2 + 18

# ---------- SAĞ ----------
RX_, RW = 2330, 590
y = 430
i2c, y = device(RX_, y, RW, "I2C kartları – plakette", "BME280 0x77 • MPU6050 0x68|MS5611 0x76 (CSB → 3.3V)",
    [(None, "VCC", "3"), (None, "GND", "g"), (None, "SDA", ("s", "21")), (None, "SCL", ("s", "22"))], "R")
for g, c in (("21", "#1a5fd0"), ("22", "#21a336")):
    xx, yy, _ = i2c[g]; e = esp_pin(g, yy, "R"); l([(e, yy), (xx, yy)], c)
t(2035, i2c["22"][1]+46, "kısa tel, ≤30-50 cm", 23, "normal", "middle", "#333")
y += 18
ds, y = device(RX_, y, RW, "Dış sıcaklık DS18B20", "ESP'nin yanında, kendi kablosu",
    [(None, "Kırmızı", "3"), (None, "Siyah", "g"), (None, "Sarı", ("s", "4"))], "R")
xx, yy, _ = ds["4"]; e = esp_pin("4", yy, "R"); l([(e, yy), (xx, yy)], "#8a2be2")
nx = 2040; dot(nx, yy); l([(nx, yy), (nx, yy-110)], "#000", 5); res_v(nx, yy-55, "4.7k", -1); pill(nx-44, yy-130, "3")
t(2040, yy+44, "su DS18B20 ile aynı GPIO4 hattı", 22, "normal", "middle", "#333")
y += 40
r(RX_, y, RW, 1730-y, "#eaf7ea", "#2a7a2a", 5)
t(RX_+RW/2, y+44, "ESP32 #3 – isik-dugumu", 32, "bold", "middle")
t(RX_+RW/2, y+80, "Capella ışık panosunun yanında", 24, "normal", "middle", "#333")
for i, s in enumerate(["ESP 1 ile kablo YOK → WiFi/MQTT", "Besleme: pano 12V → DC-DC 5V", "8'li röle kartı (ışıklar)",
                       "PIR hareket sensörü", "GPS NEO-M8N", "Dış ışık MOSFET (alarm flaşı)", "Pinler montajda netleşecek"]):
    t(RX_+28, y+130+i*40, "• " + s, 25)

# ---------- renk tablosu ----------
cy = 1815
t(60, cy+10, "Damar renkleri:", 29, "bold")
items = [("kırmızı", "5V"), ("mavi", "GND"), ("gri", "2. GND (MQ)"), ("pembe", "3.3V"),
         ("beyaz", "sinyal 1"), ("kahve", "sinyal 2"), ("yeşil", "sinyal 3"), ("sarı", "sinyal 4")]
x = 400
for d, lab in items:
    sw(x, cy, d); t(x+24, cy+9, f"{d.capitalize()}: {lab}", 25); x += 318

# ---------- notlar ----------
ny = 1928
notes = [("Bölücüler ESP tarafında (plakette)", "5V sensör çıkışı en fazla 3.3V'a indirilir.|Karavanda 5V ile ölç: pinde 3.3V'u geçmesin.|MQ: AO −10k− GPIO −20k− GND"),
         ("Kablo", "Ekran sadece ESP tarafında GND'ye; sensör|tarafında kes, makaronla kapat. Boş damarlar|iki uçta kısa kesilip yedek bırakılır."),
         ("Dikkat", "Pilli CO/LPG dedektörleri ASIL koruma, kalsın.|Tekli röle: IN'e 3.3V verince tam bırakıyor mu?|MQ'lar ilk 24-48 saat ısınma, sonra eşik.")]
nw = (W-120-60)/3
for i, (a, b) in enumerate(notes):
    x = 60 + i*(nw+30)
    r(x, ny-46, nw, 180, "#fffbe6", "#c9a400", 3, 14)
    t(x+22, ny-10, a, 27, "bold")
    for j, s in enumerate(b.split("|")): t(x+22, ny+28+j*34, s, 23)

svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="296mm" height="209mm" font-family="DejaVu Sans, sans-serif">' + "".join(o) + "</svg>"
open("genel_sema.svg", "w").write(svg)
open("genel_sema.html", "w").write('<!DOCTYPE html><html><head><meta charset="utf-8"><style>@page{size:A4 landscape;margin:0}html,body{margin:0;overflow:hidden}svg{display:block}</style></head><body>' + svg + "</body></html>")
