#!/usr/bin/env python3
"""Yerel panel simgelerini Noto Color Emoji yazı tipinden PNG olarak üretir."""
import os
from PIL import Image, ImageDraw, ImageFont
YT = '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'
HEDEF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'yerel_panel', 'simgeler')
SIMGELER = {'genel': '🏠', 'aku': '🔋', 'su': '💧', 'seviye': '📐', 'ic': '🌡️', 'nem': '💦', 'dis': '🌲',
            'basinc': '🌤️', 'hareket': '🚶', 'alarm': '🛡️', 'konak': '🏕️', 'konum': '📍',
            'volt': '⚡', 'akim': '🔌', 'guc': '💡', 'hucre': '🧪', 'bms': '📶', 'akis': '🌊',
            'takvim': '📅', 'pompa': '🚰', 'ayar': '⚙️', 'rehber': '🧭', 'karavan': '🚐'}
f = ImageFont.truetype(YT, 109)
for ad, e in SIMGELER.items():
    im = Image.new('RGBA', (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), e, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    for boy in (22, 26):
        k = im.copy()
        k.thumbnail((boy, boy), Image.LANCZOS)
        t = Image.new('RGBA', (boy, boy), (0, 0, 0, 0))
        t.paste(k, ((boy - k.width) // 2, (boy - k.height) // 2), k)
        t.save(os.path.join(HEDEF, '%s_%d.png' % (ad, boy)))
print('tamam')
