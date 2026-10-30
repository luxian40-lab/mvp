"""Generación de vista previa de plantillas de certificado (admin)."""

from __future__ import annotations

import logging
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

NOMBRE_DEMO = 'María González Pérez'
CEDULA_DEMO = '1234567890'
URL_DEMO = 'https://certificados.eki.technology/verificar-certificado/DEMO/'
ORG_DEMO = 'Organización demo'

CAMPOS_TEXTO = (
    'modo_plantilla',
    'color_primario',
    'color_secundario',
    'texto_superior',
    'texto_certificado',
    'url_plantilla_imagen',
)


def _modo_preview(plantilla, post_data: dict) -> str:
    modo = (post_data.get('modo_plantilla') or '').strip()
    if modo in ('imagen', 'diseno_eki', 'pdf'):
        return modo
    if plantilla is not None:
        return plantilla.modo_efectivo()
    return 'imagen'


def _leer_bytes_archivo(file_field) -> bytes | None:
    if not file_field:
        return None
    try:
        if hasattr(file_field, 'read'):
            data = file_field.read()
            if hasattr(file_field, 'seek'):
                file_field.seek(0)
            return data or None
        with file_field.open('rb') as fh:
            return fh.read()
    except Exception as exc:
        logger.warning('No se pudo leer imagen de plantilla: %s', exc)
        return None


def _aplicar_campos_post(plantilla, post_data: dict) -> None:
    for field in CAMPOS_TEXTO:
        if field not in post_data:
            continue
        val = post_data.get(field)
        if val is None:
            continue
        if field == 'url_plantilla_imagen':
            val = (val or '').strip() or None
        setattr(plantilla, field, val)


def _resolver_fuente_imagen(plantilla, uploaded_img=None) -> tuple[str | None, str | bytes | None]:
    if uploaded_img:
        data = _leer_bytes_archivo(uploaded_img)
        if data:
            return 'bytes', data

    # Archivo subido gana sobre URL pegada (evita plantilla antigua en S3)
    archivo = getattr(plantilla, 'archivo_plantilla_imagen', None)
    if archivo:
        try:
            archivo_url = archivo.url
            if archivo_url and str(archivo_url).startswith('http'):
                return 'url', archivo_url
        except Exception:
            pass
        data = _leer_bytes_archivo(archivo)
        if data:
            return 'bytes', data

    url = (getattr(plantilla, 'url_plantilla_imagen', None) or '').strip()
    if url:
        return 'url', url

    return None, None


def _cargar_imagen_base(*, plantilla_bytes: bytes | None = None, plantilla_url: str | None = None) -> Image.Image:
    if plantilla_bytes:
        return Image.open(BytesIO(plantilla_bytes)).convert('RGB')
    if plantilla_url:
        response = requests.get(plantilla_url, timeout=15)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert('RGB')
    raise ValueError('Falta imagen de plantilla')


def _preview_imagen_simple(
    *,
    plantilla_bytes: bytes | None = None,
    plantilla_url: str | None = None,
) -> BytesIO:
    """Muestra la plantilla base con datos demo cuando no hay marcadores RGB."""
    img = _cargar_imagen_base(plantilla_bytes=plantilla_bytes, plantilla_url=plantilla_url)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    banner_h = 72
    draw.rectangle((0, 0, img.width, banner_h), fill=(15, 23, 42))
    draw.text((16, 12), 'VISTA PREVIA', fill='white', font=font)
    draw.text((16, 34), NOMBRE_DEMO, fill='#a5f3fc', font=font)
    draw.text((16, img.height - 36), f'Cédula demo: {CEDULA_DEMO}', fill=(30, 30, 30), font=font)

    buf = BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf


def _preview_pdf_placeholder() -> BytesIO:
    img = Image.new('RGB', (900, 636), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.rectangle((24, 24, 876, 612), outline=(100, 116, 139), width=3)
    draw.text((48, 48), 'Vista previa — modo PDF', fill=(15, 23, 42), font=font)
    draw.text((48, 90), 'Sube el PDF y guarda para emitir certificados.', fill=(71, 85, 105), font=font)
    buf = BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf


def plantilla_desde_request(post_data: dict, plantilla_id: str | None = None):
    """Construye instancia PlantillaCertificado desde POST (con o sin PK)."""
    from core.models_certificados import PlantillaCertificado

    plantilla = None
    pk = (plantilla_id or post_data.get('plantilla_id') or '').strip()
    if pk.isdigit():
        plantilla = PlantillaCertificado.objects.filter(pk=int(pk)).first()

    if plantilla is None:
        plantilla = PlantillaCertificado(
            modo_plantilla=post_data.get('modo_plantilla') or 'imagen',
            color_primario=post_data.get('color_primario') or '#2C3E50',
            color_secundario=post_data.get('color_secundario') or '#3498DB',
            texto_superior=post_data.get('texto_superior') or 'eki - Soluciones Educativas',
            texto_certificado=post_data.get('texto_certificado') or 'CERTIFICADO DE FINALIZACIÓN',
            url_plantilla_imagen=(post_data.get('url_plantilla_imagen') or '').strip() or None,
        )
    else:
        _aplicar_campos_post(plantilla, post_data)

    return plantilla


def generar_preview_certificado(
    plantilla,
    post_data: dict | None = None,
    files: dict | None = None,
    *,
    nombre_estudiante: str | None = None,
    cedula_estudiante: str | None = None,
    organizacion_nombre: str | None = None,
    url_verificacion: str | None = None,
) -> BytesIO:
    """Genera PNG de vista previa según modo y campos del formulario."""
    from core.certificado_diseno_eki import render_certificado_diseno_eki
    from core.utils_certificados import generar_certificado_marcadores

    post_data = post_data or {}
    files = files or {}

    nombre = (nombre_estudiante or NOMBRE_DEMO).strip() or NOMBRE_DEMO
    cedula = (cedula_estudiante or CEDULA_DEMO).strip() or CEDULA_DEMO
    org_nom = (organizacion_nombre or ORG_DEMO).strip() or ORG_DEMO
    url_demo = (url_verificacion or URL_DEMO).strip() or URL_DEMO

    uploaded_img = files.get('archivo_plantilla_imagen')
    uploaded_fondo = files.get('imagen_fondo')
    uploaded_logo = files.get('logo_institucion')
    if uploaded_img:
        plantilla.archivo_plantilla_imagen = uploaded_img
    if uploaded_fondo:
        plantilla.imagen_fondo = uploaded_fondo
    if uploaded_logo:
        plantilla.logo_institucion = uploaded_logo

    modo = _modo_preview(plantilla, post_data)

    if modo == 'diseno_eki':
        return render_certificado_diseno_eki(plantilla=plantilla)

    if modo == 'pdf':
        return _preview_pdf_placeholder()

    kind, src = _resolver_fuente_imagen(plantilla, uploaded_img)
    if not kind or src is None:
        raise ValueError('Falta imagen de plantilla (archivo o URL S3)')

    kwargs = {
        'nombre_estudiante': nombre,
        'cedula_estudiante': cedula,
        'url_verificacion': url_demo,
        'organizacion_nombre': org_nom,
    }
    try:
        if kind == 'url':
            return generar_certificado_marcadores(plantilla_url_o_path=src, **kwargs)
        return generar_certificado_marcadores(plantilla_bytes=src, **kwargs)
    except Exception as exc:
        logger.warning('Preview con marcadores falló (%s); usando plantilla base', exc)
        return _preview_imagen_simple(
            plantilla_bytes=src if kind == 'bytes' else None,
            plantilla_url=src if kind == 'url' else None,
        )
