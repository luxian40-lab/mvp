"""Enlaces públicos por cliente: ?org=slug o ?t=token opaco."""
from __future__ import annotations

import re
import secrets
from typing import Optional

from django.conf import settings
from django.utils.text import slugify

BASE_URL = getattr(settings, 'MARGEN_PUBLIC_URL', 'https://margen.eki.technology')


def _base_url() -> str:
    return (BASE_URL or 'https://margen.eki.technology').rstrip('/')


def slug_desde_nombre(nombre: str) -> str:
    base = slugify(nombre or 'org')[:40] or 'org'
    return base


def generar_token() -> str:
    return secrets.token_urlsafe(12).replace('-', '').replace('_', '')[:20]


def obtener_o_crear_enlace(cliente) -> 'MargenEnlaceCliente':
    from calculadora_margen.models import MargenEnlaceCliente

    enlace, created = MargenEnlaceCliente.objects.get_or_create(
        cliente=cliente,
        defaults={
            'slug': _slug_unico(slug_desde_nombre(cliente.nombre)),
            'token': generar_token(),
        },
    )
    if created:
        return enlace
    changed = False
    if not enlace.slug:
        enlace.slug = _slug_unico(slug_desde_nombre(cliente.nombre), exclude_pk=enlace.pk)
        changed = True
    if not enlace.token:
        enlace.token = generar_token()
        changed = True
    if changed:
        enlace.save(update_fields=['slug', 'token'])
    return enlace


def _slug_unico(base: str, *, exclude_pk: int | None = None) -> str:
    from calculadora_margen.models import MargenEnlaceCliente

    slug = base[:40] or 'org'
    if not MargenEnlaceCliente.objects.filter(slug__iexact=slug).exclude(pk=exclude_pk).exists():
        return slug
    for i in range(2, 100):
        candidate = f'{slug[:36]}-{i}'
        if not MargenEnlaceCliente.objects.filter(slug__iexact=candidate).exclude(pk=exclude_pk).exists():
            return candidate
    return f'{slug[:30]}-{secrets.token_hex(3)}'


def resolver_cliente_id(
  *,
  org: str = '',
  token: str = '',
  cliente_id: str = '',
) -> Optional[int]:
    """Resuelve cliente desde ?org=slug, ?t=token o ?cliente=id (legacy)."""
    from calculadora_margen.models import MargenEnlaceCliente

    tok = (token or '').strip()
    if tok:
        row = MargenEnlaceCliente.objects.filter(token=tok, activo=True).select_related('cliente').first()
        return row.cliente_id if row else None

    org_slug = (org or '').strip()
    if org_slug:
        if re.fullmatch(r'\d+', org_slug):
            from core.models import Cliente
            if Cliente.objects.filter(pk=int(org_slug)).exists():
                return int(org_slug)
        row = MargenEnlaceCliente.objects.filter(slug__iexact=org_slug, activo=True).first()
        if row:
            return row.cliente_id
        # Auto-provisión: slug coincide con nombre aproximado (primer uso)
        from core.models import Cliente
        for c in Cliente.objects.all()[:500]:
            if slug_desde_nombre(c.nombre) == org_slug.lower():
                enlace = obtener_o_crear_enlace(c)
                if enlace.slug.lower() == org_slug.lower():
                    return c.pk
        return None

    raw = (cliente_id or '').strip()
    if raw.isdigit():
        from core.models import Cliente
        pk = int(raw)
        if Cliente.objects.filter(pk=pk).exists():
            return pk
    return None


def urls_margen_cliente(cliente, *, curso_id: int | None = None) -> dict[str, str]:
    """URLs listas para compartir en curso WA o portal."""
    enlace = obtener_o_crear_enlace(cliente)
    base = _base_url()
    q_curso = f'&curso={int(curso_id)}' if curso_id else ''
    return {
        'slug': enlace.slug,
        'token': enlace.token,
        'url_org': f'{base}/?org={enlace.slug}{q_curso}',
        'url_token': f'{base}/?t={enlace.token}{q_curso}',
        'url_legacy': f'{base}/?cliente={cliente.pk}{q_curso}',
    }
