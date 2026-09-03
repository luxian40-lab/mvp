"""Split screen vertical 9:16 — panel SaaS animado (typing, scroll, transiciones)."""
from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 9:16 vertical — apto celular / WA
_W = 1080
_H = 1920
_TOP_H = int(_H * 0.60)  # 1152
_BOT_H = _H - _TOP_H

_COLOR_BG = (244, 243, 248)
_COLOR_SIDEBAR = (240, 237, 245)
_COLOR_MARCA = (154, 108, 172)
_COLOR_MARCA_D = (95, 58, 110)
_COLOR_INK = (31, 31, 40)
_COLOR_MUTED = (108, 102, 120)
_COLOR_CARD = (255, 255, 255)
_COLOR_SUCCESS = (53, 166, 71)
_COLOR_BOT_BG = (29, 23, 38)


@dataclass
class _VistaUI:
    headline: str
    narracion: str
    cards: list[tuple[str, str]]
    bar_label: str
    bar_pct: float


def _font(path_candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    base = Path(__file__).resolve().parent.parent / 'fonts'
    paths = path_candidates + [
        '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
        str(base / 'DejaVuSans-Bold.ttf'),
        'C:\\Windows\\Fonts\\arialbd.ttf',
    ]
    reg_paths = [
        '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans.ttf',
        str(base / 'DejaVuSans.ttf'),
        'C:\\Windows\\Fonts\\arial.ttf',
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (IOError, OSError):
            continue
    for p in reg_paths:
        try:
            return ImageFont.truetype(p, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _fonts() -> dict[str, ImageFont.FreeTypeFont]:
    return {
        'h1': _font([], 52),
        'h2': _font([], 34),
        'body': _font([], 24),
        'small': _font([], 20),
        'badge': _font([], 18),
        'hero': _font([], 44),
    }


def _parse_punto(p: str) -> tuple[str, str]:
    p = (p or '').strip()
    for sep in (' — ', ' – ', ' - ', ': '):
        if sep in p:
            a, b = p.split(sep, 1)
            return a.strip()[:40], b.strip()[:55]
    return p[:40], ''


def _vistas_desde_contenido(titulo: str, puntos: list[str], guion: str = '') -> list[_VistaUI]:
    from core.course_engine.tarjeta_beats import beats_desde_tarjeta

    beats = beats_desde_tarjeta(titulo=titulo, puntos=puntos, guion=guion)
    vistas: list[_VistaUI] = []
    pcts = [40.0, 58.0, 76.0, 94.0, 100.0]
    for i, b in enumerate(beats):
        cards = [(c, a or b.narracion[:40]) for c, a in b.filas] if b.filas else [(b.headline[:22], b.detalle[:28] or b.narracion[:28])]
        vistas.append(
            _VistaUI(
                headline=b.headline,
                narracion=b.narracion,
                cards=cards[:3],
                bar_label='Avance lección',
                bar_pct=pcts[min(i, len(pcts) - 1)],
            )
        )
    return vistas or [
        _VistaUI(headline=titulo, narracion=titulo, cards=[('Lección', 'eki')], bar_label='Avance', bar_pct=50.0)
    ]


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 2


def _typing_text(text: str, progress: float) -> str:
    n = max(0, int(len(text) * _ease_out(progress)))
    s = text[:n]
    if n < len(text) and n > 0:
        s += '|'
    return s


def _dibujar_sidebar(draw: ImageDraw.ImageDraw, scroll_pulse: float) -> None:
    draw.rectangle([(0, 0), (72, _TOP_H)], fill=_COLOR_SIDEBAR)
    draw.line([(72, 0), (72, _TOP_H)], fill=(220, 214, 230), width=1)
    for i, y in enumerate([120, 200, 280, 360]):
        cy = y + int(4 * math.sin(scroll_pulse + i))
        draw.rounded_rectangle([(20, cy), (52, cy + 28)], radius=6, fill=_COLOR_MARCA if i == 0 else (210, 200, 220))


def _dibujar_header(draw: ImageDraw.ImageDraw, fonts: dict, vista_idx: int) -> None:
    draw.rectangle([(72, 0), (_W, 56)], fill=(255, 255, 255))
    draw.line([(72, 56), (_W, 56)], fill=(230, 226, 236), width=1)
    draw.rounded_rectangle([(96, 12), (420, 44)], radius=18, fill=_COLOR_BG, outline=(220, 214, 230))
    draw.text((112, 18), 'Buscar en el curso…', font=fonts['small'], fill=_COLOR_MUTED)
    draw.ellipse([(_W - 52, 12), (_W - 20, 44)], fill=_COLOR_MARCA)
    tabs = ['Inicio', 'Lección', 'Práctica']
    tx = 440
    for j, tab in enumerate(tabs):
        col = _COLOR_MARCA if j == min(vista_idx, 2) else _COLOR_MUTED
        draw.text((tx, 18), tab, font=fonts['small'], fill=col)
        tx += 110


def _dibujar_contenido_scroll(
    canvas: Image.Image,
    *,
    vista: _VistaUI,
    local_t: float,
    scroll_pulse: float,
    fonts: dict,
) -> None:
    """Panel principal con scroll suave y cards que entran."""
    content_h = 980
    content = Image.new('RGB', (_W - 72, content_h), _COLOR_BG)
    cd = ImageDraw.Draw(content)

    scroll_max = max(0, content_h - (_TOP_H - 56) - 40)
    scroll_base = int(scroll_max * 0.35 * _ease_out(min(1.0, local_t * 1.2)))
    scroll_wave = int(22 * math.sin(scroll_pulse * 0.6))
    scroll_y = min(scroll_max, max(0, scroll_base + scroll_wave))

    y = 24 - scroll_y
    cd.text((24, y), 'Panel educativo', font=fonts['badge'], fill=_COLOR_MARCA)
    y += 36

    typing_prog = min(1.0, local_t / 0.38)
    sub = _typing_text(vista.headline[:55], typing_prog)
    cd.text((24, y), sub, font=fonts['h2'], fill=_COLOR_INK)
    y += 56

    for i, (tit, val) in enumerate(vista.cards):
        appear = local_t - (0.22 + i * 0.14)
        if appear <= 0:
            continue
        alpha = _ease_out(min(1.0, appear / 0.25))
        card_y = y + i * 132
        highlight = i == 0 and local_t > 0.5
        fill = (248, 242, 252) if highlight else _COLOR_CARD
        cd.rounded_rectangle([(24, card_y), (_W - 120, card_y + 108)], radius=14, fill=fill, outline=(220, 210, 230))
        cd.text((44, card_y + 18), tit, font=fonts['body'], fill=_COLOR_MARCA if highlight else _COLOR_INK)
        cd.text((44, card_y + 52), val, font=fonts['small'], fill=_COLOR_MUTED)
        if highlight:
            cd.rounded_rectangle([(44, card_y + 82), (200, card_y + 98)], radius=6, fill=_COLOR_MARCA)
            cd.text((56, card_y + 80), 'Destacado', font=fonts['badge'], fill=(255, 255, 255))
        if alpha < 1.0:
            overlay = Image.new('RGBA', content.size, (244, 243, 248, int(255 * (1 - alpha))))
            content.paste(overlay, (0, 0), overlay)

    bar_y = y + 420 - scroll_y
    if local_t > 0.35:
        bar_prog = _ease_out(min(1.0, (local_t - 0.35) / 0.45))
        cd.text((24, bar_y), vista.bar_label, font=fonts['small'], fill=_COLOR_MUTED)
        cd.rounded_rectangle([(24, bar_y + 28), (_W - 120, bar_y + 44)], radius=8, fill=(225, 218, 235))
        bw = int((_W - 160) * (vista.bar_pct / 100.0) * bar_prog)
        cd.rounded_rectangle([(24, bar_y + 28), (24 + max(8, bw), bar_y + 44)], radius=8, fill=_COLOR_SUCCESS)
        cd.text((24, bar_y + 52), f'{int(vista.bar_pct * bar_prog)}%', font=fonts['badge'], fill=_COLOR_MARCA_D)

    canvas.paste(content, (72, 56))


def _dibujar_panel_superior(
    vista: _VistaUI,
    *,
    local_t: float,
    frame_idx: int,
    vista_idx: int,
) -> Image.Image:
    panel = Image.new('RGB', (_W, _TOP_H), _COLOR_BG)
    draw = ImageDraw.Draw(panel)
    fonts = _fonts()
    pulse = frame_idx * 0.12

    _dibujar_sidebar(draw, pulse)
    _dibujar_header(draw, fonts, vista_idx)
    _dibujar_contenido_scroll(panel, vista=vista, local_t=local_t, scroll_pulse=pulse, fonts=fonts)

    draw.rectangle([(0, _TOP_H - 3), (_W, _TOP_H)], fill=_COLOR_MARCA)
    return panel


def _dibujar_panel_inferior(vista: _VistaUI, *, local_t: float, frame_idx: int) -> Image.Image:
    """40% inferior — texto hero con typing (estilo Platzi)."""
    panel = Image.new('RGB', (_W, _BOT_H), _COLOR_BOT_BG)
    draw = ImageDraw.Draw(panel)
    fonts = _fonts()

    for y in range(_BOT_H):
        t = y / max(_BOT_H - 1, 1)
        r = int(29 + 40 * t)
        g = int(23 + 30 * t)
        b = int(38 + 45 * t)
        draw.line([(0, y), (_W, y)], fill=(r, g, b))

    draw.rounded_rectangle([(48, 40), (140, 76)], radius=8, fill=_COLOR_MARCA)
    draw.text((62, 48), 'eki', font=fonts['badge'], fill=(255, 255, 255))

    typing_prog = min(1.0, local_t / 0.42)
    hero = _typing_text(vista.narracion or vista.headline, typing_prog)
    kw, rest = _split_hero(hero.replace('|', ''))
    if '|' in hero and not rest:
        kw = hero

    y0 = 120
    draw.text((56, y0), kw, font=fonts['hero'], fill=_COLOR_MARCA)
    if rest:
        kw_w = draw.textbbox((0, 0), kw.replace('|', ''), font=fonts['hero'])[2]
        draw.text((56 + kw_w + 8, y0 + 8), rest, font=fonts['body'], fill=(240, 235, 248))

    if local_t > 0.55 and vista.cards:
        hint_prog = _ease_out(min(1.0, (local_t - 0.55) / 0.35))
        hint = vista.cards[0][1] if vista.cards else ''
        hint_txt = _typing_text(hint[:60], hint_prog)
        draw.text((56, y0 + 100), hint_txt, font=fonts['small'], fill=(180, 170, 195))

    dots = 3
    for i in range(dots):
        active = int(frame_idx / 8) % dots == i
        cx = 56 + i * 28
        r = 6 if active else 4
        col = _COLOR_MARCA if active else (80, 70, 95)
        draw.ellipse([(cx - r, _BOT_H - 56 - r), (cx + r, _BOT_H - 56 + r)], fill=col)

    return panel


def _split_hero(text: str) -> tuple[str, str]:
    t = (text or '').strip()
    if not t:
        return 'eki', ''
    if ':' in t:
        a, b = t.split(':', 1)
        return a.strip() + ':', b.strip()
    if '=' in t:
        a, b = t.split('=', 1)
        return a.strip(), '=' + b.strip()
    words = t.split()
    if len(words) >= 2:
        return words[0], ' '.join(words[1:])
    return t, ''


def _render_frame(
    vista: _VistaUI,
    *,
    local_t: float,
    frame_idx: int,
    vista_idx: int,
    blend_next: float = 0.0,
    vista_next: _VistaUI | None = None,
) -> Image.Image:
    top = _dibujar_panel_superior(vista, local_t=local_t, frame_idx=frame_idx, vista_idx=vista_idx)
    bot = _dibujar_panel_inferior(vista, local_t=local_t, frame_idx=frame_idx)
    frame = Image.new('RGB', (_W, _H))
    frame.paste(top, (0, 0))
    frame.paste(bot, (0, _TOP_H))

    if blend_next > 0.01 and vista_next is not None:
        top_n = _dibujar_panel_superior(vista_next, local_t=0.05, frame_idx=frame_idx + 1, vista_idx=vista_idx + 1)
        bot_n = _dibujar_panel_inferior(vista_next, local_t=0.05, frame_idx=frame_idx + 1)
        nxt = Image.new('RGB', (_W, _H))
        nxt.paste(top_n, (0, 0))
        nxt.paste(bot_n, (0, _TOP_H))
        frame = Image.blend(frame, nxt, alpha=min(1.0, blend_next))

    return frame


def generar_frames_split_vertical(
    *,
    titulo: str,
    puntos: list[str],
    salida_dir: Path,
    duracion_seg: float,
    fps: int = 15,
    guion: str = '',
) -> list[Path]:
    """
    Genera secuencia PNG 1080x1920 sincronizada al audio.
    Panel superior 60%: UI SaaS con scroll, typing y cards.
    Panel inferior 40%: hero con texto animado.
    """
    duracion_seg = max(1.0, float(duracion_seg))
    fps = max(10, min(24, int(fps)))
    total_frames = max(int(duracion_seg * fps), fps)

    vistas = _vistas_desde_contenido(titulo, puntos, guion=guion)
    n_vistas = len(vistas)
    frames_por_vista = max(fps, total_frames // n_vistas)
    trans_frames = max(3, fps // 4)

    salida_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    out_idx = 0

    for v_idx, vista in enumerate(vistas):
        vista_next = vistas[v_idx + 1] if v_idx + 1 < n_vistas else None
        n_local = frames_por_vista if v_idx < n_vistas - 1 else (total_frames - out_idx)

        for f in range(n_local):
            if out_idx >= total_frames:
                break
            local_t = f / max(n_local - 1, 1)
            blend = 0.0
            if vista_next and f >= n_local - trans_frames:
                blend = (f - (n_local - trans_frames)) / max(trans_frames, 1)

            img = _render_frame(
                vista,
                local_t=local_t,
                frame_idx=out_idx,
                vista_idx=v_idx,
                blend_next=blend,
                vista_next=vista_next,
            )
            path = salida_dir / f'frame_{out_idx:05d}.png'
            img.save(path, format='PNG', optimize=True)
            if path.stat().st_size > 3000:
                paths.append(path)
            out_idx += 1

    while out_idx < total_frames and paths:
        last = paths[-1]
        extra = salida_dir / f'frame_{out_idx:05d}.png'
        shutil.copy(last, extra)
        paths.append(extra)
        out_idx += 1

    return paths
