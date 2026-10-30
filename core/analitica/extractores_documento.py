"""Extracción robusta de texto para indexación RAG (PDF agrícolas, cartillas, etc.)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

from django.conf import settings

logger = logging.getLogger(__name__)

_MIN_TEXTO_UTIL = 40


def _ocr_disponible() -> bool:
    if not getattr(settings, 'RAG_PDF_OCR_ENABLED', True):
        return False
    if shutil.which('tesseract'):
        return True
    try:
        import pytesseract  # noqa: F401

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extraer_texto_pdf(ruta: str) -> tuple[str, str]:
    """
    Extrae texto de un PDF con varias estrategias.
    Returns: (texto, metodo) — metodo para logs/diagnóstico.
    """
    texto = ''
    metodo = ''

    t1 = _extraer_pymupdf(ruta)
    if len(t1.strip()) >= _MIN_TEXTO_UTIL:
        return t1.strip(), 'pymupdf'

    t2 = _extraer_pypdf2(ruta)
    if len(t2.strip()) > len(t1.strip()):
        texto, metodo = t2.strip(), 'pypdf2'
    else:
        texto, metodo = t1.strip(), 'pymupdf_parcial'

    if len(texto.strip()) >= _MIN_TEXTO_UTIL:
        return texto.strip(), metodo

    if _ocr_disponible():
        t3 = _extraer_pdf_ocr(ruta)
        if len(t3.strip()) > len(texto.strip()):
            texto = t3.strip()
            metodo = 'ocr_tesseract'
            if len(texto) >= _MIN_TEXTO_UTIL:
                return texto, metodo

    return texto.strip(), metodo or 'sin_texto'


def extraer_texto_archivo(ruta: str) -> tuple[str, str]:
    """Punto único para RAG: PDF, DOCX, TXT, Excel."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext == '.pdf':
        return extraer_texto_pdf(ruta)
    if ext == '.docx':
        return _extraer_docx(ruta), 'docx'
    if ext == '.txt':
        return _extraer_txt(ruta), 'txt'
    if ext in ('.xlsx', '.xlsm', '.xls'):
        from core.rag_eki_multitenant import RAGClienteCurso

        return RAGClienteCurso._extraer_xlsx(ruta), 'xlsx'
    return '', f'no_soportado:{ext}'


def _extraer_pymupdf(ruta: str) -> str:
    try:
        import fitz

        partes: list[str] = []
        with fitz.open(ruta) as doc:
            for page in doc:
                partes.append(page.get_text('text') or '')
                if len(''.join(partes)) > 500_000:
                    break
        return '\n'.join(partes)
    except Exception as exc:
        logger.debug('[Extract] pymupdf falló %s: %s', ruta, exc)
        return ''


def _extraer_pypdf2(ruta: str) -> str:
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(ruta)
        if getattr(reader, 'is_encrypted', False):
            try:
                reader.decrypt('')
            except Exception:
                pass
        return '\n'.join((p.extract_text() or '') for p in reader.pages)
    except Exception as exc:
        logger.debug('[Extract] PyPDF2 falló %s: %s', ruta, exc)
        return ''


def _extraer_pdf_ocr(ruta: str) -> str:
    max_pages = int(getattr(settings, 'RAG_PDF_OCR_MAX_PAGES', 12) or 12)
    max_pages = max(1, min(max_pages, 30))
    try:
        import fitz
        import pytesseract
        from PIL import Image

        lang = getattr(settings, 'RAG_PDF_OCR_LANG', 'spa+eng')
        partes: list[str] = []
        with fitz.open(ruta) as doc:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                pix = page.get_pixmap(dpi=150, alpha=False)
                img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                txt = pytesseract.image_to_string(img, lang=lang) or ''
                if txt.strip():
                    partes.append(txt.strip())
        return '\n\n'.join(partes)
    except Exception as exc:
        logger.warning('[Extract] OCR falló %s: %s', os.path.basename(ruta), exc)
        return ''


def _extraer_docx(ruta: str) -> str:
    try:
        from docx import Document

        doc = Document(ruta)
        return '\n'.join(p.text for p in doc.paragraphs if p.text)
    except Exception as exc:
        logger.error('[Extract] DOCX %s: %s', ruta, exc)
        return ''


def _extraer_txt(ruta: str) -> str:
    for enc in ('utf-8', 'latin-1', 'cp1252'):
        try:
            with open(ruta, 'r', encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return ''


def diagnostico_pdf(ruta: str) -> dict:
    """Info rápida para admin/soporte."""
    info: dict = {'ruta': os.path.basename(ruta), 'paginas': 0, 'metodo': '', 'chars': 0}
    try:
        import fitz

        with fitz.open(ruta) as doc:
            info['paginas'] = doc.page_count
    except Exception:
        pass
    texto, metodo = extraer_texto_pdf(ruta)
    info['metodo'] = metodo
    info['chars'] = len(texto)
    info['ocr_disponible'] = _ocr_disponible()
    if texto:
        info['muestra'] = texto[:200].replace('\n', ' ')
    return info
