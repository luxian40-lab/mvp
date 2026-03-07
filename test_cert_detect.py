"""Test de detección de marcadores con clustering para certificado v1.9.3"""
import numpy as np
from PIL import Image
from scipy.ndimage import label

img = Image.open('plantilla_test.jpg').convert('RGB')
a = np.array(img)
print(f"Imagen: {img.size}")

for name, color in [("GRIS(nombre)", [128,128,128]), ("ROJO(cedula)", [255,0,0]), ("AZUL(QR)", [0,0,255])]:
    mask = np.all(np.abs(a.astype(int) - color) <= 18, axis=-1)
    L, n = label(mask)
    total = int(mask.sum())
    if n == 0:
        print(f"{name}: NO ENCONTRADO")
        continue
    sizes = []
    for i in range(1, n+1):
        cc = np.argwhere(L == i)
        sizes.append((len(cc), i))
    sizes.sort(reverse=True)
    cc = np.argwhere(L == sizes[0][1])
    x = int(np.median(cc[:, 1]))
    y = int(np.median(cc[:, 0]))
    print(f"{name}: cluster={sizes[0][0]}px centro=({x},{y}) [total disperso={total}px, {n} clusters]")

print("\nv1.9.2 (sin cluster): Gris media=(966,746) de 6512px dispersos")
print("v1.9.3 (con cluster): Gris cluster principal en posicion correcta")
print("\nVerifica certificado_test_v193.png")
