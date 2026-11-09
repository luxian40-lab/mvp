"""Enlace y QR de registro de la línea 3.

Arma la dirección wa.me y la frase que viaja en ella. No lee ni escribe
la conversación: el webhook no importa este módulo.
El número sale de EKI_LINEA_REGISTRO_E164. Vacío = no hay enlace.
"""
from __future__ import annotations

import io
from urllib.parse import quote

FRASE_GENERAL = 'HOLA EKI'
TOKEN_GENERAL = 'registro-general'
# El enlace de Agricapital no muestra el id. EKI C26 sigue abriendo lo mismo.
# La frase canónica del QR la pisa admin con frase_para_cliente si hay setting.
_ALIAS_CLIENTE = {26: 'Hola, AgriCapital me invitó a un curso gratis'}


def numero_registro() -> str:
    from django.conf import settings

    bruto = getattr(settings, 'EKI_LINEA_REGISTRO_E164', '') or ''
    return ''.join(c for c in str(bruto) if c.isdigit())


def frase_de_cliente(cliente_id: int) -> str:
    """Frase del enlace. El id sigue sirviendo si el alias cambia."""
    alias = _ALIAS_CLIENTE.get(int(cliente_id))
    if alias:
        return alias
    return f'EKI C{int(cliente_id)}'


def leer_frase(frase: str) -> tuple[str, int | None] | None:
    """('general', None), ('cliente', id) o None si no es una frase de registro."""
    texto = ' '.join((frase or '').split()).upper()
    if texto == FRASE_GENERAL:
        return ('general', None)
    for cliente_id, alias in _ALIAS_CLIENTE.items():
        if texto == alias.upper():
            return ('cliente', cliente_id)
    if not texto.startswith('EKI C'):
        return None
    resto = texto[5:]
    if not resto.isdigit():
        return None
    return ('cliente', int(resto))


def token_de_cliente(cliente_id: int | None) -> str:
    """Marca que vuelve con el Flow. El cliente no se pregunta en el formulario."""
    if cliente_id is None:
        return TOKEN_GENERAL
    return f'registro-C{int(cliente_id)}'


def destino_de_token(token: str) -> tuple[str, int | None] | None:
    """('general', None), ('cliente', id) o None si no es un Flow de registro."""
    marca = (token or '').strip()
    if marca == TOKEN_GENERAL:
        return ('general', None)
    if not marca.startswith('registro-C'):
        return None
    resto = marca[len('registro-C'):]
    if not resto.isdigit():
        return None
    return ('cliente', int(resto))


def enlace_whatsapp(frase: str) -> str:
    numero = numero_registro()
    limpia = ' '.join((frase or '').split())
    if not numero or not limpia:
        return ''
    return f'https://wa.me/{numero}?text={quote(limpia)}'


def png_qr(url: str) -> bytes:
    import qrcode

    imagen = qrcode.make(url)
    salida = io.BytesIO()
    imagen.save(salida, format='PNG')
    return salida.getvalue()
