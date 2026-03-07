"""Test v1.9.3 - detección sin scipy, genera certificado de prueba"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

TOLERANCIA = 18

def encontrar_marcador_v193(np_img, color, tol=TOLERANCIA):
    """Misma lógica que utils_certificados.py v1.9.3 - sin scipy"""
    mask = np.all(np.abs(np_img.astype(int) - np.array(color)) <= tol, axis=-1)
    coords = np.argwhere(mask)
    if coords.size == 0:
        return None
    total = len(coords)
    if total < 50:
        y = int(np.median(coords[:,0])); x = int(np.median(coords[:,1]))
        print(f"  {color}: {total}px directo -> ({x},{y})")
        return x, y
    
    BLOCK = 30
    h, w = np_img.shape[:2]
    cols_b = (w + BLOCK - 1) // BLOCK
    by = coords[:,0] // BLOCK; bx = coords[:,1] // BLOCK
    bids = by * cols_b + bx
    uniq, cnt = np.unique(bids, return_counts=True)
    best_i = np.argmax(cnt); bid = uniq[best_i]
    cby = (bid // cols_b) * BLOCK + BLOCK // 2
    cbx = (bid % cols_b) * BLOCK + BLOCK // 2
    RADIO = 30
    nearby = (np.abs(coords[:,0]-cby)<=RADIO) & (np.abs(coords[:,1]-cbx)<=RADIO)
    cc = coords[nearby]
    if len(cc) < 3:
        y = int(np.median(coords[:,0])); x = int(np.median(coords[:,1]))
        print(f"  {color}: {total}px fallback -> ({x},{y})")
        return x, y
    y = int(np.median(cc[:,0])); x = int(np.median(cc[:,1]))
    print(f"  {color}: {total}px total, cluster={len(cc)}px -> ({x},{y})")
    return x, y

img = Image.open('plantilla_test.jpg').convert('RGB')
np_img = np.array(img)
print(f"Imagen: {img.size}")

pos_n = encontrar_marcador_v193(np_img, (128,128,128))
pos_c = encontrar_marcador_v193(np_img, (255,0,0))
pos_q = encontrar_marcador_v193(np_img, (0,0,255))

print(f"\nPosiciones: Nombre={pos_n}, Cedula={pos_c}, QR={pos_q}")

# Generar certificado test
draw = ImageDraw.Draw(img)
h = img.size[1]
for pos in [pos_n, pos_c, pos_q]:
    if pos:
        x, y = pos
        cf = img.getpixel((max(x-25,0), min(y+25,h-1)))
        draw.ellipse([x-20,y-20,x+20,y+20], fill=cf)

fonts = os.path.join('core','fonts')
fn = ImageFont.truetype(os.path.join(fonts,'GreatVibes-Regular.ttf'), 80)
fc = ImageFont.truetype(os.path.join(fonts,'GreatVibes-Regular.ttf'), 40)
draw.text((pos_n[0],pos_n[1]), 'Julian Ramirez', font=fn, fill='black', anchor='ms')
draw.text((pos_c[0],pos_c[1]), '1014310196', font=fc, fill='black', anchor='ms')
img.save('certificado_test_v193.png')
print("\nCertificado guardado: certificado_test_v193.png")
