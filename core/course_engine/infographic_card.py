"""Lámina educativa eki — fondo visual + texto legible (estilo Platzi)."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

_W = 1280
_H = 720
_COLOR_MARCA = (154, 108, 172)
_COLOR_MARCA_OSCURO = (88, 58, 102)
_COLOR_PANEL = (255, 255, 255, 235)
_COLOR_TEXTO = (28, 28, 36)
_COLOR_FONDO_PLATZI = (252, 252, 252)
_COLOR_TABLA_HEAD = (154, 108, 172)
_COLOR_TABLA_ROW = (245, 242, 248)
_COLOR_TABLA_ROW_NEW = (232, 220, 240)


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _fuentes_platzi() -> dict[str, ImageFont.FreeTypeFont]:
    """Tipografía grande estilo Platzi (hero + tabla)."""
    base = Path(__file__).resolve().parent.parent / 'fonts'
    candidatas = [
        '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf',
        '/usr/share/fonts/liberation/LiberationSans-Bold.ttf',
        str(base / 'DejaVuSans-Bold.ttf'),
        'C:\\Windows\\Fonts\\arialbd.ttf',
    ]
    regular = [
        '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans.ttf',
        str(base / 'DejaVuSans.ttf'),
        'C:\\Windows\\Fonts\\arial.ttf',
    ]
    bold_path = next((p for p in candidatas if Path(p).is_file() or p.startswith('C:')), candidatas[0])
    reg_path = next((p for p in regular if Path(p).is_file() or p.startswith('C:')), regular[0])
    try:
        return {
            'hero': _load_font(bold_path, 78),
            'hero_sub': _load_font(reg_path, 40),
            'table_head': _load_font(bold_path, 26),
            'table_cell': _load_font(reg_path, 24),
            'badge': _load_font(bold_path, 20),
        }
    except (IOError, OSError):
        d = ImageFont.load_default()
        return {'hero': d, 'hero_sub': d, 'table_head': d, 'table_cell': d, 'badge': d}


def _fuentes_sans() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """Sans-serif legible — Linux EB, Windows y repo."""
    base = Path(__file__).resolve().parent.parent / 'fonts'
    candidatas = [
        ('/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf', 46, 30, 22),
        ('/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf', 46, 30, 22),
        ('/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf', 44, 28, 22),
        ('/usr/share/fonts/liberation/LiberationSans-Bold.ttf', 44, 28, 22),
        ('/usr/share/fonts/google-noto-sans-fonts/NotoSans-Bold.ttf', 44, 28, 22),
        (str(base / 'DejaVuSans-Bold.ttf'), 46, 30, 22),
        ('C:\\Windows\\Fonts\\arialbd.ttf', 44, 28, 22),
        ('C:\\Windows\\Fonts\\arial.ttf', 42, 26, 20),
    ]
    for path, s_t, s_p, s_b in candidatas:
        try:
            return (
                ImageFont.truetype(path, s_t),
                ImageFont.truetype(path, s_p),
                ImageFont.truetype(path, s_b),
            )
        except (IOError, OSError):
            continue
    gv = base / 'GreatVibes-Regular.ttf'
    if gv.is_file():
        try:
            return (
                ImageFont.truetype(str(gv), 54),
                ImageFont.truetype(str(gv), 38),
                ImageFont.truetype(str(gv), 30),
            )
        except (IOError, OSError):
            pass
    d = ImageFont.load_default()
    return d, d, d


def _split_hero_titulo(titulo: str) -> tuple[str, str]:
    """Divide título estilo Platzi: palabra clave grande + resto."""
    t = (titulo or 'eki').strip()
    if ':' in t:
        a, b = t.split(':', 1)
        return a.strip(), f': {b.strip()}'
    if '=' in t:
        a, b = t.split('=', 1)
        return a.strip(), f'= {b.strip()}'
    palabras = t.split()
    if len(palabras) >= 3:
        return ' '.join(palabras[:2]), ' '.join(palabras[2:])
    if len(palabras) == 2:
        return palabras[0], palabras[1]
    return t[: min(28, len(t))], t[min(28, len(t)):].strip()


def _parse_punto_tabla(punto: str) -> tuple[str, str]:
    """Separa concepto | detalle para fila de tabla."""
    p = (punto or '').strip()
    for sep in (' — ', ' – ', ' - ', ': '):
        if sep in p:
            a, b = p.split(sep, 1)
            return a.strip()[:36], b.strip()[:48]
    palabras = p.split()
    if len(palabras) > 5:
        mid = len(palabras) // 2
        return ' '.join(palabras[:mid])[:36], ' '.join(palabras[mid:])[:48]
    return p[:36], ''


def _dibujar_logo_eki(draw: ImageDraw.ImageDraw, fonts: dict) -> None:
    draw.rounded_rectangle([(48, 40), (130, 72)], radius=8, fill=_COLOR_MARCA)
    draw.text((62, 46), 'eki', font=fonts['badge'], fill=(255, 255, 255))


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


# Velocidad legible en pantalla (~10–12 caracteres/s efectivos)
_CHARS_POR_SEG_TYPING = 10.5
_TYPING_SHARE_BEAT = 0.82  # % del beat en animación; resto hold con texto completo
_MIN_FRAMES_TYPING = 14
_MIN_FRAMES_HOLD = 6
_FPS_PLATZI = 15


def _typing_text(text: str, progress: float) -> str:
    """Progreso de escritura — palabra a palabra con fracción suave en la palabra activa."""
    t = (text or '').strip()
    if not t:
        return ''
    if progress >= 1.0:
        return t
    if progress <= 0:
        return ''

    words = t.split()
    if len(words) == 1:
        n = max(0, int(len(t) * _smoothstep(progress)))
        return t[:n]

    pos = progress * len(words)
    n_full = int(pos)
    n_full = min(n_full, len(words))
    out = ' '.join(words[:n_full])
    if n_full < len(words):
        frac = pos - n_full
        next_w = words[n_full]
        take = max(1, int(len(next_w) * _smoothstep(frac))) if frac > 0.05 else 0
        if take:
            out = f'{out} {next_w[:take]}'.strip()
    return out


def _chars_en_beat(beat) -> int:
    n = len((beat.narracion or '').strip())
    n += len((beat.detalle or '').strip())
    if beat.filas:
        _, acc = beat.filas[-1]
        n += len((acc or '').strip())
    return max(n, 24)


def _frames_para_beat(beat, fps: int, *, min_per: int = 10) -> int:
    chars = _chars_en_beat(beat)
    typing_frames = max(_MIN_FRAMES_TYPING, int((chars / _CHARS_POR_SEG_TYPING) * fps))
    hold = max(_MIN_FRAMES_HOLD, int(0.45 * fps))
    return max(min_per, typing_frames + hold)


def _typing_progress_en_beat(frame_idx: int, frames_total: int) -> float:
    """0→1 en los primeros _TYPING_SHARE_BEAT del beat; luego 1.0 (hold)."""
    if frames_total <= 1:
        return 1.0
    typing_frames = max(
        _MIN_FRAMES_TYPING,
        min(int(frames_total * _TYPING_SHARE_BEAT), frames_total - _MIN_FRAMES_HOLD),
    )
    if frame_idx >= typing_frames:
        return 1.0
    return _smoothstep(frame_idx / max(typing_frames - 1, 1))


def _badge_ancho(draw: ImageDraw.ImageDraw, texto: str, font, *, pad: int = 28, max_w: int = 420) -> int:
    bb = draw.textbbox((0, 0), (texto or '')[:32], font=font)
    return min(max(bb[2] - bb[0] + pad, 90), max_w)


def _render_platzi_beat(
    canvas: Image.Image,
    beat,
    *,
    typing: float = 1.0,
) -> None:
    """Lámina Platzi 16:9 — texto vivo alineado al guion TTS."""
    from core.course_engine.tarjeta_beats import TarjetaBeat

    assert isinstance(beat, TarjetaBeat)
    draw = ImageDraw.Draw(canvas)
    fonts = _fuentes_platzi()
    _dibujar_logo_eki(draw, fonts)

    badge = (beat.headline or 'eki · lección')[:42]
    badge_draw = badge[:32]
    bx1 = 56
    bx2 = bx1 + _badge_ancho(draw, badge_draw, fonts['badge'])
    draw.rounded_rectangle([(bx1, 36), (bx2, 68)], radius=8, fill=_COLOR_MARCA)
    draw.text((68, 42), badge_draw, font=fonts['badge'], fill=(255, 255, 255))

    narr_visible = _typing_text(beat.narracion, _smoothstep(min(1.0, typing / 0.48)))
    y = 92
    for linea in _wrap_lineas(draw, narr_visible, fonts['hero_sub'], _W - 140):
        draw.text((80, y), linea, font=fonts['hero_sub'], fill=_COLOR_TEXTO)
        y += 42

    tabla_bottom = y
    if beat.filas:
        tabla_x, tabla_y = 80, max(y + 16, 200)
        tabla_w = _W - 160
        col_w = tabla_w // 2
        head_h = 44
        row_h = 52
        draw.rounded_rectangle(
            [(tabla_x, tabla_y), (tabla_x + tabla_w, tabla_y + head_h)],
            radius=8,
            fill=_COLOR_TABLA_HEAD,
        )
        draw.text((tabla_x + 20, tabla_y + 10), 'Concepto', font=fonts['table_head'], fill=(255, 255, 255))
        draw.text((tabla_x + col_w + 20, tabla_y + 10), 'Detalle', font=fonts['table_head'], fill=(255, 255, 255))
        for i, (concepto, accion) in enumerate(beat.filas):
            ry = tabla_y + head_h + i * row_h
            es_nueva = i == len(beat.filas) - 1 and typing > 0.38
            bg = _COLOR_TABLA_ROW_NEW if es_nueva else _COLOR_TABLA_ROW
            draw.rectangle([(tabla_x, ry), (tabla_x + tabla_w, ry + row_h)], fill=bg)
            draw.text((tabla_x + 20, ry + 14), concepto[:36], font=fonts['table_cell'], fill=_COLOR_TEXTO)
            if accion:
                if es_nueva:
                    acc_t = max(0.0, typing - 0.38)
                    prog_acc = _smoothstep(min(1.0, acc_t / 0.38))
                    accion_txt = _typing_text(accion, prog_acc)
                else:
                    accion_txt = accion[:48]
                draw.text((tabla_x + col_w + 20, ry + 14), accion_txt, font=fonts['table_cell'], fill=_COLOR_TEXTO)
        tabla_bottom = tabla_y + head_h + len(beat.filas) * row_h
        draw.rounded_rectangle(
            [(tabla_x, tabla_y), (tabla_x + tabla_w, tabla_bottom)],
            radius=10,
            outline=(200, 190, 210),
            width=2,
        )

    if beat.detalle and typing > 0.62:
        det_t = max(0.0, typing - 0.62)
        det = _typing_text(beat.detalle, _smoothstep(min(1.0, det_t / 0.38)))
        det_y = min(tabla_bottom + 18, _H - 56)
        for linea in _wrap_lineas(draw, det, fonts['badge'], _W - 160)[:2]:
            draw.text((80, det_y), linea, font=fonts['badge'], fill=_COLOR_MARCA_OSCURO)
            det_y += 26


def _render_platzi_frame(
    canvas: Image.Image,
    *,
    titulo: str,
    puntos: list[str],
    paso: int,
) -> None:
    """
    Lámina estilo Platzi: fondo claro, hero grande, tabla que crece fila a fila.
    paso 0 = solo hero; paso 1 = hero + cabecera tabla; paso 2+ = +1 fila.
    """
    draw = ImageDraw.Draw(canvas)
    fonts = _fuentes_platzi()
    keyword, resto = _split_hero_titulo(titulo)

    _dibujar_logo_eki(draw, fonts)

    hero_y = 120 if paso == 0 else 88
    draw.text((80, hero_y), keyword, font=fonts['hero'], fill=_COLOR_MARCA)
    kw_w = draw.textbbox((0, 0), keyword, font=fonts['hero'])[2]
    if resto:
        draw.text((80 + kw_w + 12, hero_y + 28), resto, font=fonts['hero_sub'], fill=_COLOR_TEXTO)

    if paso == 0:
        return

    tabla_x, tabla_y = 80, 260 if paso == 1 else 230
    tabla_w = _W - 160
    col_w = tabla_w // 2
    head_h = 44
    row_h = 52

    draw.rounded_rectangle(
        [(tabla_x, tabla_y), (tabla_x + tabla_w, tabla_y + head_h)],
        radius=8,
        fill=_COLOR_TABLA_HEAD,
    )
    draw.text((tabla_x + 20, tabla_y + 10), 'Concepto', font=fonts['table_head'], fill=(255, 255, 255))
    draw.text((tabla_x + col_w + 20, tabla_y + 10), 'Acción', font=fonts['table_head'], fill=(255, 255, 255))

    filas_visibles = max(0, paso - 1)
    for i in range(filas_visibles):
        ry = tabla_y + head_h + i * row_h
        es_nueva = i == filas_visibles - 1
        bg = _COLOR_TABLA_ROW_NEW if es_nueva else _COLOR_TABLA_ROW
        draw.rectangle([(tabla_x, ry), (tabla_x + tabla_w, ry + row_h)], fill=bg)
        draw.line([(tabla_x, ry + row_h), (tabla_x + tabla_w, ry + row_h)], fill=(220, 214, 228), width=1)
        draw.line([(tabla_x + col_w, ry), (tabla_x + col_w, ry + row_h)], fill=(220, 214, 228), width=1)

        concepto, accion = _parse_punto_tabla(puntos[i])
        offset_x = 18 if es_nueva else 0
        draw.text((tabla_x + 20 + offset_x, ry + 14), concepto, font=fonts['table_cell'], fill=_COLOR_TEXTO)
        if accion:
            draw.text((tabla_x + col_w + 20 + offset_x, ry + 14), accion, font=fonts['table_cell'], fill=_COLOR_TEXTO)

    draw.rounded_rectangle(
        [(tabla_x, tabla_y), (tabla_x + tabla_w, tabla_y + head_h + filas_visibles * row_h)],
        radius=10,
        outline=(200, 190, 210),
        width=2,
    )


def _canvas_platzi() -> Image.Image:
    img = Image.new('RGB', (_W, _H), _COLOR_FONDO_PLATZI)
    draw = ImageDraw.Draw(img)
    for y in range(_H):
        t = y / max(_H - 1, 1)
        r = int(252 - 4 * t)
        g = int(252 - 6 * t)
        b = int(252 - 8 * t)
        draw.line([(0, y), (_W, y)], fill=(r, g, b))
    draw.line([(0, 0), (_W, 0)], fill=_COLOR_MARCA, width=4)
    return img


def _wrap_lineas(draw, texto: str, font, max_ancho: int) -> list[str]:
    palabras = (texto or '').split()
    lineas: list[str] = []
    cur: list[str] = []
    for w in palabras:
        trial = ' '.join(cur + [w])
        if draw.textbbox((0, 0), trial, font=font)[2] > max_ancho and cur:
            lineas.append(' '.join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lineas.append(' '.join(cur))
    return lineas[:3]


def _gradiente_marca(img: Image.Image) -> None:
    """Fondo degradado morado cuando no hay foto de contexto."""
    draw = ImageDraw.Draw(img)
    for y in range(_H):
        t = y / max(_H - 1, 1)
        r = int(_COLOR_MARCA_OSCURO[0] * (1 - t) + _COLOR_MARCA[0] * t * 0.6)
        g = int(_COLOR_MARCA_OSCURO[1] * (1 - t) + _COLOR_MARCA[1] * t * 0.6)
        b = int(_COLOR_MARCA_OSCURO[2] * (1 - t) + _COLOR_MARCA[2] * t * 0.6)
        draw.line([(0, y), (_W, y)], fill=(r, g, b))


def _aplicar_fondo_foto(base: Image.Image, fondo_path: Path) -> None:
    try:
        foto = Image.open(fondo_path).convert('RGB')
        foto = foto.resize((_W, _H), Image.Resampling.LANCZOS)
        foto = foto.filter(ImageFilter.GaussianBlur(radius=14))
        osc = Image.new('RGB', (_W, _H), (40, 28, 48))
        base.paste(Image.blend(foto, osc, alpha=0.55))
    except Exception as exc:
        logger.warning('Fondo foto lámina: %s', exc)
        _gradiente_marca(base)


def _dibujar_icono_punto(draw: ImageDraw.ImageDraw, cx: int, cy: int, idx: int) -> None:
    """Ícono simple por punto (círculo + pictograma)."""
    r = 22
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=_COLOR_MARCA)
    # Mini pictograma según índice
    if idx == 0:
        draw.rectangle([(cx - 10, cy - 6), (cx + 10, cy + 8)], outline=(255, 255, 255), width=2)
        draw.line([(cx - 6, cy - 2), (cx + 6, cy - 2)], fill=(255, 255, 255), width=2)
    elif idx == 1:
        draw.ellipse([(cx - 8, cy - 8), (cx + 8, cy + 8)], outline=(255, 255, 255), width=2)
        draw.line([(cx, cy - 4), (cx, cy + 4)], fill=(255, 255, 255), width=2)
    else:
        draw.polygon([(cx, cy - 8), (cx + 8, cy + 6), (cx - 8, cy + 6)], outline=(255, 255, 255))


def generar_fondo_lamina_ia(
    run_dir: Path,
    *,
    titulo: str,
    escena_visual: str = '',
    categoria_visual: str = 'finanzas',
    openai_client=None,
) -> Optional[Path]:
    """
    Fondo visual 16:9 vía IA — íconos y ambiente educativo SIN texto
    (el texto legible va en capa Pillow encima).
    """
    escena = (escena_visual or titulo or 'gestión financiera rural').strip()[:400]
    cat = (categoria_visual or 'finanzas').strip()
    prompt = (
        f'Professional e-learning presentation slide BACKGROUND only, 16:9 widescreen. '
        f'Topic: {titulo[:200]}. Context: {escena}. '
        f'Style: modern Platzi/Coursera infographic, purple brand accent #9A6CAC, '
        f'flat icons (notebook, calculator, team handshake, chart), '
        f'rich visual depth, illustrated educational atmosphere, '
        f'dark-to-light purple gradient, high contrast, NOT blank white. '
        f'Category: {cat}. '
        f'CRITICAL: absolutely NO text, NO letters, NO numbers, NO watermarks, NO logos.'
    )
    ph = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:12]
    out_dir = run_dir / 'images'
    out_dir.mkdir(parents=True, exist_ok=True)
    local_path = out_dir / f'lamina_fondo_{ph}.png'
    if local_path.is_file():
        return local_path

    try:
        from django.conf import settings

        if openai_client is None:
            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        model = getattr(settings, 'COURSE_ENGINE_IMAGE_MODEL', 'gpt-image-1')
        quality = getattr(settings, 'COURSE_ENGINE_IMAGE_QUALITY', '') or 'medium'
        if 'dall-e' in model.lower():
            quality = 'standard'

        size = '1536x1024'
        kwargs = {
            'model': model,
            'prompt': prompt[:4000],
            'size': size,
            'n': 1,
        }
        if quality:
            kwargs['quality'] = quality
        resp = openai_client.images.generate(**kwargs)
        item = resp.data[0]
        data = None
        if getattr(item, 'b64_json', None):
            import base64

            data = base64.b64decode(item.b64_json)
        elif getattr(item, 'url', None):
            import httpx

            dl = httpx.get(item.url, timeout=90, follow_redirects=True)
            dl.raise_for_status()
            data = dl.content
        if not data:
            return None
        local_path.write_bytes(data)
        return local_path
    except Exception as exc:
        logger.warning('generar_fondo_lamina_ia: %s', exc)
        return None


def _render_tarjeta_en_canvas(
    canvas: Image.Image,
    *,
    titulo: str,
    puntos: list[str],
    max_puntos: int | None = None,
) -> None:
    """Dibuja panel + título + hasta max_puntos bullets (None = todos)."""
    overlay = Image.new('RGBA', (_W, _H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    margen_x, margen_y = 56, 48
    panel_w = _W - margen_x * 2
    panel_h = _H - margen_y * 2
    od.rounded_rectangle(
        [(margen_x, margen_y), (margen_x + panel_w, margen_y + panel_h)],
        radius=20,
        fill=_COLOR_PANEL,
    )
    composed = Image.alpha_composite(canvas.convert('RGBA'), overlay).convert('RGB')
    canvas.paste(composed)
    draw = ImageDraw.Draw(canvas)
    font_titulo, font_punto, font_badge = _fuentes_sans()

    draw.rectangle([(margen_x, margen_y), (margen_x + panel_w, margen_y + 10)], fill=_COLOR_MARCA)
    badge = 'eki · lección'
    draw.rounded_rectangle(
        [(margen_x + 24, margen_y + 24), (margen_x + 200, margen_y + 58)],
        radius=8,
        fill=_COLOR_MARCA,
    )
    draw.text((margen_x + 36, margen_y + 30), badge, font=font_badge, fill=(255, 255, 255))

    y = margen_y + 78
    for linea in _wrap_lineas(draw, titulo, font_titulo, panel_w - 80):
        draw.text((margen_x + 32, y), linea, font=font_titulo, fill=_COLOR_TEXTO)
        y += 50

    visibles = puntos if max_puntos is None else puntos[: max(0, max_puntos)]
    y = max(y + 20, margen_y + 200)
    for i, punto in enumerate(visibles):
        cx = margen_x + 48
        cy = y + 22
        _dibujar_icono_punto(draw, cx, cy, i)
        py = y
        for linea in _wrap_lineas(draw, punto, font_punto, panel_w - 100):
            draw.text((margen_x + 88, py), linea, font=font_punto, fill=_COLOR_TEXTO)
            py += 36
        y = py + 18


def _fondo_tarjeta(
    *,
    titulo: str,
    fondo_imagen: Optional[Path],
    run_dir: Optional[Path],
    escena_visual: str,
    categoria_visual: str,
    usar_fondo_ia: bool,
) -> Image.Image:
    canvas = Image.new('RGB', (_W, _H))
    fondo_ok = False
    if usar_fondo_ia and run_dir is not None:
        ia = generar_fondo_lamina_ia(
            run_dir,
            titulo=titulo,
            escena_visual=escena_visual,
            categoria_visual=categoria_visual,
        )
        if ia and ia.is_file():
            _aplicar_fondo_foto(canvas, ia)
            fondo_ok = True
    if not fondo_ok and fondo_imagen and fondo_imagen.is_file():
        _aplicar_fondo_foto(canvas, fondo_imagen)
        fondo_ok = True
    if not fondo_ok:
        _gradiente_marca(canvas)
    return canvas


def _generar_frames_platzi(
    *,
    titulo: str,
    puntos: list[str],
    guion: str,
    salida_dir: Path,
    duracion_seg: float = 0,
    fps: int = _FPS_PLATZI,
) -> list[Path]:
    from core.course_engine.tarjeta_beats import beats_desde_tarjeta

    beats = beats_desde_tarjeta(titulo=titulo, puntos=puntos, guion=guion)
    salida_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    if duracion_seg > 0:
        total_budget = max(int(duracion_seg * fps), len(beats) * _MIN_FRAMES_TYPING)
        raw_counts = [_frames_para_beat(b, fps) for b in beats]
        raw_sum = sum(raw_counts) or 1
        if raw_sum > total_budget:
            counts = [
                max(_MIN_FRAMES_TYPING + _MIN_FRAMES_HOLD, int(c * total_budget / raw_sum))
                for c in raw_counts
            ]
            # Ajuste fino por redondeo
            diff = total_budget - sum(counts)
            if counts and diff:
                counts[-1] = max(counts[-1] + diff, _MIN_FRAMES_TYPING + _MIN_FRAMES_HOLD)
        else:
            counts = list(raw_counts)
            extra = total_budget - sum(counts)
            if counts and extra > 0:
                counts[-1] += extra

        idx = 0
        for beat, per in zip(beats, counts):
            for f in range(per):
                t = _typing_progress_en_beat(f, per)
                canvas = _canvas_platzi()
                _render_platzi_beat(canvas, beat, typing=t)
                path = salida_dir / f'frame_{idx:05d}.png'
                canvas.save(path, format='PNG', optimize=True)
                if path.stat().st_size > 4000:
                    paths.append(path)
                idx += 1
        while idx < total_budget and paths:
            import shutil

            extra = salida_dir / f'frame_{idx:05d}.png'
            shutil.copy(paths[-1], extra)
            paths.append(extra)
            idx += 1
        return paths

    for i, beat in enumerate(beats):
        canvas = _canvas_platzi()
        _render_platzi_beat(canvas, beat, typing=1.0)
        path = salida_dir / f'tarjeta_platzi_{i:02d}.png'
        canvas.save(path, format='PNG', optimize=True)
        if path.is_file() and path.stat().st_size > 4000:
            paths.append(path)
    return paths


def generar_frames_tarjeta_animada(
    *,
    titulo: str,
    puntos: list[str],
    salida_dir: Path,
    fondo_imagen: Optional[Path] = None,
    run_dir: Optional[Path] = None,
    escena_visual: str = '',
    categoria_visual: str = 'finanzas',
    usar_fondo_ia: bool = False,
    estilo: str = 'platzi',
    duracion_seg: float = 6.0,
    fps: int = _FPS_PLATZI,
    guion: str = '',
) -> list[Path]:
    """
    Secuencia PNG progresiva.
    estilo platzi (default): 16:9 — texto vivo alineado al guion TTS.
    estilo split_vertical: 9:16 split screen (experimental).
    """
    titulo = (titulo or 'eki').strip()[:120]
    puntos_limpios = [str(p).strip()[:90] for p in (puntos or []) if str(p).strip()][:4]
    if not puntos_limpios:
        puntos_limpios = ['Punto clave de la lección']

    salida_dir.mkdir(parents=True, exist_ok=True)

    if estilo == 'split_vertical':
        from core.course_engine.split_screen_ui import generar_frames_split_vertical

        return generar_frames_split_vertical(
            titulo=titulo,
            puntos=puntos_limpios,
            salida_dir=salida_dir,
            duracion_seg=duracion_seg,
            fps=fps,
            guion=guion,
        )

    if estilo == 'platzi':
        return _generar_frames_platzi(
            titulo=titulo,
            puntos=puntos_limpios,
            guion=guion,
            salida_dir=salida_dir,
            duracion_seg=duracion_seg,
            fps=fps,
        )

    frames: list[Path] = []
    base = _fondo_tarjeta(
        titulo=titulo,
        fondo_imagen=fondo_imagen,
        run_dir=run_dir,
        escena_visual=escena_visual,
        categoria_visual=categoria_visual,
        usar_fondo_ia=usar_fondo_ia,
    )

    for n in range(len(puntos_limpios) + 1):
        frame = base.copy()
        _render_tarjeta_en_canvas(frame, titulo=titulo, puntos=puntos_limpios, max_puntos=n)
        path = salida_dir / f'tarjeta_anim_{n:02d}.png'
        frame.save(path, format='PNG', optimize=True)
        if path.is_file() and path.stat().st_size > 4000:
            frames.append(path)
    return frames


def generar_tarjeta_infografica(
    *,
    titulo: str,
    puntos: list[str],
    salida: Path,
    subtitulo: str = '',
    fondo_imagen: Optional[Path] = None,
    run_dir: Optional[Path] = None,
    escena_visual: str = '',
    categoria_visual: str = 'finanzas',
    usar_fondo_ia: bool = True,
) -> bool:
    """
    PNG 1280x720 — lámina didáctica con fondo visual + panel de texto legible.
    """
    titulo = (titulo or 'eki').strip()[:120]
    puntos_limpios = [str(p).strip()[:90] for p in (puntos or []) if str(p).strip()][:4]
    if not puntos_limpios:
        puntos_limpios = ['Punto clave de la lección']

    salida.parent.mkdir(parents=True, exist_ok=True)
    canvas = _canvas_platzi()
    _render_platzi_frame(
        canvas,
        titulo=titulo,
        puntos=puntos_limpios,
        paso=len(puntos_limpios),
    )

    try:
        canvas.save(salida, format='PNG', optimize=True)
        return salida.is_file() and salida.stat().st_size > 8000
    except Exception as exc:
        logger.exception('generar_tarjeta_infografica: %s', exc)
        return False
