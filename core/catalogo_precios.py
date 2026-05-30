"""
Consulta estructurada de precios comerciales en Postgres para Nat.

Los precios viven en tablas relacionales (no en RAG vectorial) para respuestas
deterministas cuando el usuario pregunta por catálogo o cotización.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Sequence

from django.db.models import Q
from django.utils import timezone

_PATRON_CATALOGO = re.compile(
    r"precio|precios|cotiz|lista|tarifa|valor|cu[aá]nto|cuesta|insumo|producto|"
    r"cat[aá]logo|bulto|arroba|\bkg\b|kilo|dosis|paquete|mezcla|fertil|herbic|fungic",
    re.I,
)


def es_consulta_catalogo(pregunta: str) -> bool:
    return bool(_PATRON_CATALOGO.search((pregunta or "").strip()))


def _tokens_busqueda(pregunta: str, max_tokens: int = 8) -> list[str]:
    raw = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]{3,}", (pregunta or "").lower())
    stop = {
        "precio", "precios", "cuanto", "cuánto", "cuesta", "valor", "lista",
        "catalogo", "catálogo", "producto", "productos", "cotiz", "cotiza",
        "cotización", "cotizacion", "necesito", "quiero", "dame", "para",
    }
    out: list[str] = []
    for tok in raw:
        if tok in stop:
            continue
        if tok not in out:
            out.append(tok)
        if len(out) >= max_tokens:
            break
    return out


def buscar_precios(
    cliente_ids: Sequence[int],
    pregunta: str,
    *,
    limite: int = 10,
):
    """
    Busca productos activos con vigencia actual para los clientes indicados.
    Prioriza cliente específico sobre catálogo general (cliente_id nulo).
    """
    from core.models import ProductoComercial

    hoy = timezone.localdate()
    ids: list[int | None] = []
    for raw in cliente_ids or []:
        try:
            cid = int(raw)
        except (TypeError, ValueError):
            continue
        if cid == 0:
            if None not in ids:
                ids.append(None)
        elif cid not in ids:
            ids.append(cid)

    if not ids:
        ids = [None]

    base = ProductoComercial.objects.filter(activo=True).filter(
        Q(vigencia_desde__isnull=True) | Q(vigencia_desde__lte=hoy),
        Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=hoy),
    )

    scope_q = Q()
    for cid in ids:
        if cid is None:
            scope_q |= Q(cliente__isnull=True)
        else:
            scope_q |= Q(cliente_id=cid)
    qs = base.filter(scope_q)

    tokens = _tokens_busqueda(pregunta)
    if tokens:
        filtro = Q()
        for tok in tokens:
            filtro |= (
                Q(nombre__icontains=tok)
                | Q(sku__icontains=tok)
                | Q(categoria__icontains=tok)
                | Q(presentacion__icontains=tok)
            )
        qs = qs.filter(filtro)

    limite = max(1, min(int(limite or 10), 25))
    productos = list(qs.order_by("-fecha_actualizacion")[: limite * 3])

    def _prio(p) -> tuple:
        cid = p.cliente_id
        preferido = ids[0] if ids else None
        if preferido is None:
            match = 0 if cid is None else 1
        else:
            match = 0 if cid == preferido else (1 if cid is None else 2)
        return (match, -(p.fecha_actualizacion.timestamp() if p.fecha_actualizacion else 0))

    productos.sort(key=_prio)
    return productos[:limite]


def _fmt_precio(valor: Decimal | None, moneda: str) -> str:
    if valor is None:
        return "—"
    mon = (moneda or "COP").upper()
    if mon == "COP":
        return f"${int(valor):,}".replace(",", ".")
    return f"{valor:,.2f} {mon}"


def formatear_contexto_precios(productos) -> str:
    """Texto tabular para inyectar al prompt de Nat (fuente oficial)."""
    if not productos:
        return ""

    lineas = [
        "LISTA DE PRECIOS OFICIAL (PostgreSQL — use SOLO estas cifras; no invente ni redondee):",
        "SKU | Producto | Presentación | Precio | Unidad | Notas",
    ]
    for p in productos:
        cliente_txt = p.cliente.nombre if p.cliente_id else "General"
        notas = (p.notas or "").strip().replace("\n", " ")[:120]
        lineas.append(
            f"{p.sku} | {p.nombre} | {p.presentacion or '—'} | "
            f"{_fmt_precio(p.precio, p.moneda)} | {p.unidad or '—'} | "
            f"[{cliente_txt}] {notas}".strip()
        )
    return "\n".join(lineas)
