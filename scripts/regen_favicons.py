"""Regenera favicons eki: SVG + PNG nítidos (sin wordmark a 16–48px)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "static" / "favicons"

ADMIN_BG = (15, 23, 42)
ADMIN_ACCENT = (20, 184, 166)
ADMIN_FG = (248, 250, 252)

PORTAL_BG = (122, 78, 142)
PORTAL_FG = (244, 242, 247)

APRENDE_BG = (122, 78, 142)
APRENDE_FG = (255, 255, 255)
APRENDE_DOT = (232, 213, 240)

STUDIO_BG = (21, 128, 61)
STUDIO_FG = (255, 247, 237)
STUDIO_ACCENT = (253, 186, 116)

CERT_BG = (95, 58, 110)
CERT_FG = (250, 250, 252)
CERT_ACCENT = (154, 108, 172)


def _round_rect(draw, xy, r, fill):
    draw.rounded_rectangle(xy, radius=r, fill=fill)


def draw_admin(draw: ImageDraw.ImageDraw, s: int):
    r = max(2, s // 8)
    _round_rect(draw, (0, 0, s - 1, s - 1), r, ADMIN_BG)
    bar_w = max(2, s // 8)
    draw.rectangle((0, 0, bar_w - 1, s - 1), fill=ADMIN_ACCENT)
    x0 = int(s * 0.34)
    y0 = int(s * 0.28)
    w = int(s * 0.42)
    h = int(s * 0.44)
    t = max(2, s // 10)
    draw.rectangle((x0, y0, x0 + w, y0 + t), fill=ADMIN_FG)
    draw.rectangle((x0, y0, x0 + t, y0 + h), fill=ADMIN_FG)
    draw.rectangle((x0, y0 + h // 2 - t // 2, x0 + int(w * 0.72), y0 + h // 2 + t // 2), fill=ADMIN_FG)
    draw.rectangle((x0, y0 + h - t, x0 + w, y0 + h), fill=ADMIN_FG)


def draw_portal(draw: ImageDraw.ImageDraw, s: int):
    """Dos figuras claras (32px): sin wordmark ni tres siluetas apretadas."""
    r = max(3, s // 5)
    _round_rect(draw, (0, 0, s - 1, s - 1), r, PORTAL_BG)
    head_r = max(3, int(s * 0.14))
    for cx_f, cy_f in ((0.34, 0.34), (0.66, 0.34)):
        cx, cy = int(s * cx_f), int(s * cy_f)
        draw.ellipse((cx - head_r, cy - head_r, cx + head_r, cy + head_r), fill=PORTAL_FG)
        tw, th = int(s * 0.18), int(s * 0.28)
        ty = cy + head_r + max(1, s // 28)
        draw.rounded_rectangle(
            (cx - tw, ty, cx + tw, ty + th),
            radius=max(2, s // 14),
            fill=PORTAL_FG,
        )


def draw_aprende(draw: ImageDraw.ImageDraw, s: int):
    r = max(3, s // 5)
    _round_rect(draw, (0, 0, s - 1, s - 1), r, APRENDE_BG)
    x0, y0 = int(s * 0.28), int(s * 0.18)
    x1, y1 = int(s * 0.78), int(s * 0.82)
    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=max(2, s // 16),
        outline=APRENDE_FG,
        width=max(2, s // 12),
    )
    for i in range(4):
        yy = int(y0 + (y1 - y0) * (0.18 + i * 0.2))
        draw.line((x0, yy, int(s * 0.18), yy), fill=APRENDE_FG, width=max(2, s // 14))
    cr = max(2, int(s * 0.10))
    cx, cy = int(s * 0.52), int(s * 0.44)
    draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=APRENDE_DOT)


def draw_studio(draw: ImageDraw.ImageDraw, s: int):
    r = max(2, s // 10)
    _round_rect(draw, (0, 0, s - 1, s - 1), r, STUDIO_BG)
    m = max(2, s // 12)
    draw.rounded_rectangle(
        (int(s * 0.22), int(s * 0.22), int(s * 0.78), int(s * 0.78)),
        radius=max(2, s // 14),
        outline=STUDIO_FG,
        width=m,
    )
    draw.ellipse(
        (int(s * 0.55), int(s * 0.32), int(s * 0.70), int(s * 0.47)),
        fill=STUDIO_ACCENT,
    )
    pts = [
        (int(s * 0.28), int(s * 0.70)),
        (int(s * 0.42), int(s * 0.48)),
        (int(s * 0.55), int(s * 0.62)),
        (int(s * 0.68), int(s * 0.45)),
        (int(s * 0.78), int(s * 0.70)),
    ]
    draw.polygon(pts, fill=STUDIO_FG)


def draw_cert(draw: ImageDraw.ImageDraw, s: int):
    r = max(3, s // 5)
    _round_rect(draw, (0, 0, s - 1, s - 1), r, CERT_BG)
    draw.rounded_rectangle(
        (int(s * 0.22), int(s * 0.18), int(s * 0.72), int(s * 0.62)),
        radius=max(2, s // 16),
        fill=CERT_FG,
    )
    for i, w in enumerate((0.70, 0.55, 0.45)):
        y = int(s * (0.30 + i * 0.10))
        draw.line(
            (int(s * 0.30), y, int(s * (0.30 + w * 0.35)), y),
            fill=CERT_ACCENT,
            width=max(2, s // 16),
        )
    cr = max(4, int(s * 0.18))
    cx, cy = int(s * 0.68), int(s * 0.68)
    draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=CERT_ACCENT)
    ir = max(2, int(cr * 0.55))
    draw.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), outline=CERT_FG, width=max(1, s // 20))


DRAWERS = {
    "admin": draw_admin,
    "portal": draw_portal,
    "aprende": draw_aprende,
    "studio": draw_studio,
    "certificados": draw_cert,
}

SVGS = {
    "admin": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki admin">
  <rect width="32" height="32" rx="4" fill="#0f172a"/>
  <rect x="0" y="0" width="4" height="32" fill="#14b8a6"/>
  <path d="M11 9.5h12v2.6H15.2v2.1H18.6v2.4H15.2V22.5H11V9.5z" fill="#f8fafc"/>
</svg>
""",
    "portal": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki portal">
  <rect width="32" height="32" rx="9" fill="#7a4e8e"/>
  <circle cx="12" cy="11" r="4" fill="#f4f2f7"/>
  <circle cx="20" cy="11" r="4" fill="#f4f2f7"/>
  <path d="M6 24c1.4-4 3.8-6 6-6s4.6 2 6 6" fill="#f4f2f7"/>
  <path d="M14 24c1.4-4 3.8-6 6-6s4.6 2 6 6" fill="#f4f2f7"/>
</svg>
""",
    "aprende": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki aprende">
  <rect width="32" height="32" rx="8" fill="#7A4E8E"/>
  <rect x="9" y="6" width="15" height="20" rx="2.2" fill="none" stroke="#FFFFFF" stroke-width="2.6"/>
  <path d="M9 11H6.2M9 15.5H6.2M9 20H6.2M9 24H6.2" stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round"/>
  <circle cx="16.5" cy="14" r="3.2" fill="#E8D5F0"/>
</svg>
""",
    "studio": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki studio">
  <rect width="32" height="32" rx="3" fill="#15803d"/>
  <rect x="7" y="7" width="18" height="18" rx="2" fill="none" stroke="#fff7ed" stroke-width="2.4"/>
  <circle cx="20" cy="13" r="2.4" fill="#fdba74"/>
  <path d="M9 23l5-8 4 5 3-5 5 8H9z" fill="#fff7ed"/>
</svg>
""",
    "certificados": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="eki certificados">
  <rect width="32" height="32" rx="7" fill="#5F3A6E"/>
  <rect x="7" y="6" width="16" height="14" rx="1.5" fill="#FAFAFC"/>
  <path d="M10 10h10M10 13.2h7M10 16.4h5" stroke="#7a4e8e" stroke-width="1.6" stroke-linecap="round"/>
  <circle cx="21" cy="21" r="6" fill="#9A6CAC"/>
  <circle cx="21" cy="21" r="3.5" fill="none" stroke="#FAFAFC" stroke-width="1.3"/>
</svg>
""",
}

# master PNG size por superficie
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
