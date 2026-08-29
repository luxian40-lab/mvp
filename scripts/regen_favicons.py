"""Regenera favicons eki: marcas DISTINTAS por producto (no clones genéricos).

Cada superficie tiene forma + color propios legibles a 32px.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "static" / "favicons"

# Paletas — portal≠aprende (antes ambos morados y se leían iguales)
ADMIN_BG = (154, 108, 172)  # #9A6CAC marca eki
ADMIN_FG = (250, 247, 252)
ADMIN_DEEP = (90, 58, 110)

PORTAL_BG = (122, 78, 142)
PORTAL_FG = (250, 247, 252)
PORTAL_ACCENT = (232, 213, 240)

APRENDE_BG = (30, 64, 175)  # índigo — aula, distinto del portal
APRENDE_FG = (255, 255, 255)
APRENDE_ACCENT = (147, 197, 253)

STUDIO_BG = (22, 101, 52)
STUDIO_FG = (255, 247, 237)
STUDIO_ACCENT = (253, 186, 116)

CERT_BG = (88, 28, 135)
CERT_FG = (250, 250, 252)
CERT_GOLD = (234, 179, 8)
CERT_ACCENT = (154, 108, 172)


def _round_rect(draw, xy, r, fill):
    draw.rounded_rectangle(xy, radius=r, fill=fill)


def draw_admin(draw: ImageDraw.ImageDraw, s: int):
    """Marca eki: tres siluetas en morado, fondo transparente (no recuadro negro)."""
    fill = ADMIN_BG

    def head(cx, cy, r):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)

    def torso(cx, top, half_w, h):
        draw.rounded_rectangle(
            (cx - half_w, top, cx + half_w, top + h),
            radius=max(2, half_w // 2),
            fill=fill,
        )

    head(int(s * 0.50), int(s * 0.28), int(s * 0.11))
    head(int(s * 0.26), int(s * 0.36), int(s * 0.09))
    head(int(s * 0.74), int(s * 0.36), int(s * 0.09))
    torso(int(s * 0.50), int(s * 0.40), int(s * 0.20), int(s * 0.52))
    torso(int(s * 0.24), int(s * 0.48), int(s * 0.15), int(s * 0.44))
    torso(int(s * 0.76), int(s * 0.48), int(s * 0.15), int(s * 0.44))


def draw_portal(draw: ImageDraw.ImageDraw, s: int):
    """Edificio B2B / org — no siluetas genéricas de 'personas'."""
    r = max(3, s // 6)
    _round_rect(draw, (0, 0, s - 1, s - 1), r, PORTAL_BG)
    # edificio
    bx0, by0 = int(s * 0.28), int(s * 0.30)
    bx1, by1 = int(s * 0.72), int(s * 0.78)
    draw.rounded_rectangle((bx0, by0, bx1, by1), radius=max(2, s // 20), fill=PORTAL_FG)
    # ventanas 2x3
    ww, wh = max(2, int(s * 0.08)), max(2, int(s * 0.08))
    for row in range(3):
        for col in range(2):
            x = bx0 + int(s * 0.10) + col * int(s * 0.18)
            y = by0 + int(s * 0.10) + row * int(s * 0.14)
            draw.rectangle((x, y, x + ww, y + wh), fill=PORTAL_BG)
    # puerta
    dw = int(s * 0.12)
    draw.rectangle(
        (cx := s // 2 - dw // 2, int(s * 0.62), cx + dw, by1),
        fill=PORTAL_BG,
    )
    # acento techo
    draw.polygon(
        [(bx0 - 2, by0), (s // 2, int(s * 0.18)), (bx1 + 2, by0)],
        fill=PORTAL_ACCENT,
    )


def draw_aprende(draw: ImageDraw.ImageDraw, s: int):
    """Libro abierto índigo — aula, no portal."""
    r = max(3, s // 6)
    _round_rect(draw, (0, 0, s - 1, s - 1), r, APRENDE_BG)
    mid = s // 2
    y0, y1 = int(s * 0.28), int(s * 0.72)
    # tapa izq / der
    draw.polygon(
        [(mid, y0), (int(s * 0.18), int(s * 0.36)), (int(s * 0.18), y1), (mid, int(s * 0.64))],
        fill=APRENDE_FG,
    )
    draw.polygon(
        [(mid, y0), (int(s * 0.82), int(s * 0.36)), (int(s * 0.82), y1), (mid, int(s * 0.64))],
        fill=APRENDE_ACCENT,
    )
    draw.line([(mid, y0), (mid, int(s * 0.64))], fill=APRENDE_BG, width=max(2, s // 16))
    # marca de página
    draw.ellipse(
        (int(s * 0.42), int(s * 0.40), int(s * 0.58), int(s * 0.56)),
        fill=APRENDE_BG,
    )


def draw_studio(draw: ImageDraw.ImageDraw, s: int):
    """Objetivo/cámara verde — vitrina creativa."""
    r = max(2, s // 10)
    _round_rect(draw, (0, 0, s - 1, s - 1), r, STUDIO_BG)
    # cuerpo cámara
    draw.rounded_rectangle(
        (int(s * 0.18), int(s * 0.34), int(s * 0.82), int(s * 0.72)),
        radius=max(2, s // 14),
        fill=STUDIO_FG,
    )
    # flash
    draw.rounded_rectangle(
        (int(s * 0.28), int(s * 0.24), int(s * 0.48), int(s * 0.36)),
        radius=max(1, s // 20),
        fill=STUDIO_ACCENT,
    )
    # lente
    cx, cy = int(s * 0.52), int(s * 0.53)
    cr = int(s * 0.16)
    draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=STUDIO_BG)
    ir = int(cr * 0.45)
    draw.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), fill=STUDIO_ACCENT)


def draw_cert(draw: ImageDraw.ImageDraw, s: int):
    """Sello + diploma — verificación pública."""
    r = max(3, s // 6)
    _round_rect(draw, (0, 0, s - 1, s - 1), r, CERT_BG)
    # diploma
    draw.rounded_rectangle(
        (int(s * 0.18), int(s * 0.20), int(s * 0.62), int(s * 0.68)),
        radius=max(2, s // 18),
        fill=CERT_FG,
    )
    for i, w in enumerate((0.55, 0.42, 0.32)):
        y = int(s * (0.32 + i * 0.10))
        draw.line(
            (int(s * 0.26), y, int(s * (0.26 + w * 0.5)), y),
            fill=CERT_ACCENT,
            width=max(2, s // 18),
        )
    # sello dorado
    cr = max(5, int(s * 0.20))
    cx, cy = int(s * 0.68), int(s * 0.62)
    draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=CERT_GOLD)
    ir = max(2, int(cr * 0.45))
    draw.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), outline=CERT_FG, width=max(2, s // 18))
    # cinta
    draw.polygon(
        [(cx - 3, cy + cr - 2), (cx - 8, int(s * 0.88)), (cx, cy + cr + 2)],
        fill=CERT_ACCENT,
    )
    draw.polygon(
        [(cx + 3, cy + cr - 2), (cx + 8, int(s * 0.88)), (cx, cy + cr + 2)],
        fill=CERT_GOLD,
    )


DRAWERS = {
    "admin": draw_admin,
    "portal": draw_portal,
    "aprende": draw_aprende,
    "studio": draw_studio,
    "certificados": draw_cert,
}

SVGS = {
    "admin": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki">
  <circle cx="10" cy="12.2" r="3.1" fill="#9A6CAC"/>
  <circle cx="16" cy="9.4" r="3.6" fill="#9A6CAC"/>
  <circle cx="22" cy="12.4" r="2.8" fill="#9A6CAC"/>
  <path fill="#9A6CAC" d="M4.2 26.5c0-5.2 2.6-8.6 6.2-8.6 1.4 0 2.6.5 3.6 1.4C15 17.6 16.4 16.8 18 16.8c4.2 0 7.2 3.6 7.2 8.7v1.2H4.2v-1.2z"/>
</svg>
""",
    "portal": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki portal">
  <rect width="32" height="32" rx="7" fill="#7a4e8e"/>
  <polygon points="6,12 16,6 26,12" fill="#e8d5f0"/>
  <rect x="9" y="12" width="14" height="14" rx="1.5" fill="#faf7fc"/>
  <rect x="12" y="15" width="3" height="3" fill="#7a4e8e"/>
  <rect x="17" y="15" width="3" height="3" fill="#7a4e8e"/>
  <rect x="12" y="20" width="3" height="3" fill="#7a4e8e"/>
  <rect x="17" y="20" width="3" height="3" fill="#7a4e8e"/>
  <rect x="14" y="22" width="4" height="4" fill="#7a4e8e"/>
</svg>
""",
    "aprende": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki aprende">
  <rect width="32" height="32" rx="7" fill="#1e40af"/>
  <path d="M16 8 L7 12 v12 l9-4 9 4 V12 Z" fill="none"/>
  <path d="M16 8 L7 12 v12 l9-4 Z" fill="#ffffff"/>
  <path d="M16 8 L25 12 v12 l-9-4 Z" fill="#93c5fd"/>
  <line x1="16" y1="8" x2="16" y2="20" stroke="#1e40af" stroke-width="1.8"/>
  <circle cx="16" cy="15" r="2.4" fill="#1e40af"/>
</svg>
""",
    "studio": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki studio">
  <rect width="32" height="32" rx="4" fill="#166534"/>
  <rect x="5" y="11" width="22" height="14" rx="2.5" fill="#fff7ed"/>
  <rect x="8" y="7" width="8" height="5" rx="1.2" fill="#fdba74"/>
  <circle cx="16" cy="18" r="5.5" fill="#166534"/>
  <circle cx="16" cy="18" r="2.6" fill="#fdba74"/>
</svg>
""",
    "certificados": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki certificados">
  <rect width="32" height="32" rx="7" fill="#581c87"/>
  <rect x="5" y="6" width="15" height="16" rx="1.5" fill="#fafafc"/>
  <path d="M8 11h9M8 14.5h7M8 18h5" stroke="#9A6CAC" stroke-width="1.6" stroke-linecap="round"/>
  <circle cx="22" cy="20" r="7" fill="#eab308"/>
  <circle cx="22" cy="20" r="3.5" fill="none" stroke="#fafafc" stroke-width="1.5"/>
  <path d="M20 26 l-2 5 3-1.5 3 1.5 -2-5" fill="#9A6CAC"/>
</svg>
""",
}

MASTER_SIZE = {
    "admin": 192,
    "studio": 192,
    "portal": 512,
    "aprende": 512,
    "certificados": 192,
}


def render_png(name: str, size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    DRAWERS[name](draw, size)
    return img


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name in DRAWERS:
        (ROOT / f"{name}.svg").write_text(SVGS[name], encoding="utf-8")
        for size in (32, 48, 180, 192):
            render_png(name, size).save(ROOT / f"{name}-{size}.png", optimize=True)
        render_png(name, MASTER_SIZE[name]).save(ROOT / f"{name}.png", optimize=True)
        print(f"OK {name}")


if __name__ == "__main__":
    main()
