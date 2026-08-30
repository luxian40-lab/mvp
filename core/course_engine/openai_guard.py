"""Validación OpenAI sin importar utils_ia (evita PyPDF2 en CLI local)."""
from __future__ import annotations

from django.conf import settings


def validar_openai_disponible(modelo: str = 'gpt-4o-mini') -> None:
    if not getattr(settings, 'OPENAI_API_KEY', None):
        raise ValueError('OPENAI_API_KEY no configurada')
    if not (modelo or '').strip():
        raise ValueError('modelo IA vacío')
