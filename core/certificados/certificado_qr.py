"""QR del diploma: módulos de tamaño entero, sin interpolar.

Un QR de ~40 módulos reescalado a 110 px con LANCZOS queda gris y borroso.
Aquí el box_size es un entero que cabe en el lado pedido; si sobra, se rellena
de blanco. Nunca se usa resize interpolado.
"""
from __future__ import annotations

from PIL import Image


def png_qr_nitido(data: str, lado: int, *, border: int = 2) -> Image.Image:
    """Imagen RGB (lado × lado), solo negro y blanco."""
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    lado = max(21, int(lado))
    payload = (data or '').strip() or 'https://certificados.eki.technology/verificar/'
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=1,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    n = qr.modules_count + 2 * border
    qr.box_size = max(1, lado // n)
    img = qr.make_image(fill_color='black', back_color='white')
    if not isinstance(img, Image.Image):
        img = img.get_image()
    img = img.convert('RGB')
    w, h = img.size
    if w == lado and h == lado:
        return img
    canvas = Image.new('RGB', (lado, lado), (255, 255, 255))
    if w > lado or h > lado:
        canvas.paste(img, (0, 0))
        return canvas
    canvas.paste(img, ((lado - w) // 2, (lado - h) // 2))
    return canvas
