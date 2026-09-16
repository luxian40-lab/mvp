# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import ssl
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

OUT = Path('static/portal/fabrica')
OUT.mkdir(parents=True, exist_ok=True)
ctx = ssl.create_default_context()

req = urllib.request.Request(
    'https://www.eki.com.co/programas',
    headers={'User-Agent': 'Mozilla/5.0 (compatible; eki-mvp/1.0)'},
)
html = urllib.request.urlopen(req, context=ctx, timeout=45).read().decode('utf-8', 'replace')

srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, flags=re.I)
srcs += re.findall(r'<img[^>]+data-src=["\']([^"\']+)["\']', html, flags=re.I)
srcs += re.findall(r'srcset=["\']([^"\']+)["\']', html, flags=re.I)

urls = []
seen = set()
for s in srcs:
    for part in s.split(','):
        u = part.strip().split(' ')[0].strip()
        if not u or u.startswith('data:'):
            continue
        if u.startswith('/'):
            u = 'https://www.eki.com.co' + u
        if u.startswith('//'):
            u = 'https:' + u
        key = u.split('?')[0]
        if key in seen:
            continue
        seen.add(key)
        low = key.lower()
        if any(x in low for x in ('logo', 'favicon', 'icon', 'sprite', 'svg', '1x1', 'pixel', 'avatar')):
            continue
        if not any(low.endswith(ext) or ext in low for ext in ('.jpg', '.jpeg', '.png', '.webp', '/media/', 'assets/')):
            continue
        urls.append(u)

log = Path('scripts/_programas_imgs.txt')
log.write_text('\n'.join(urls), encoding='utf-8')
print('candidates', len(urls))

# Prefer program-looking filenames
keywords = [
    ('emprend', 'card_emprendimiento.jpg'),
    ('maquin', 'card_maquinaria.jpg'),
    ('comerci', 'card_comercial.jpg'),
    ('digital', 'card_digital.jpg'),
    ('dinero', 'card_dinero.jpg'),
    ('riendas', 'card_dinero.jpg'),
    ('agro', 'card_emprendimiento.jpg'),
    ('campo', 'card_maquinaria.jpg'),
    ('venta', 'card_comercial.jpg'),
    ('ia', 'card_digital.jpg'),
]

picked: dict[str, str] = {}
for u in urls:
    low = u.lower()
    for kw, name in keywords:
        if kw in low and name not in picked:
            picked[name] = u
            break

# Fill remaining with largest downloads among remaining urls
order = [
    'card_emprendimiento.jpg',
    'card_maquinaria.jpg',
    'card_comercial.jpg',
    'card_digital.jpg',
    'card_dinero.jpg',
]

def download(u: str) -> bytes | None:
    try:
        r = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        data = urllib.request.urlopen(r, context=ctx, timeout=30).read()
        if len(data) < 5000:
            return None
        return data
    except Exception as e:
        print('fail', type(e).__name__, u[:90])
        return None

saved = {}
for name in order:
    u = picked.get(name)
    if u:
        data = download(u)
        if data:
            saved[name] = data
            print('kw', name, len(data), u[:90])

for u in urls:
    if len(saved) >= 5:
        break
    for name in order:
        if name in saved:
            continue
        data = download(u)
        if data:
            saved[name] = data
            print('fill', name, len(data), u[:90])
            break

for name, data in saved.items():
    im = Image.open(BytesIO(data)).convert('RGB')
    im = im.resize((640, 360), Image.Resampling.LANCZOS)
    dest = OUT / name
    im.save(dest, quality=88)
    print('wrote', dest)
