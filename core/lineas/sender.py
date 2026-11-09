"""Sender por línea: envía por el phone id y la WABA de esa línea.

No cambia `twilio.rest.Client`. Cada llamada fija el phone id de salida solo
mientras dura el envío, así dos líneas pueden enviar en el mismo hilo.
Ningún módulo del ciclo de imports debe importar este archivo: pide el
Sender con `sender_de_linea` desde arriba (tareas, webhooks, admin).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Protocol


class Sender(Protocol):
    canal: str

    def texto(self, telefono: str, texto: str, *, media_url: str | None = None, agente: str = '') -> dict: ...

    def botones(self, telefono: str, texto: str, botones: list[tuple[str, str]], *, agente: str = '') -> dict: ...

    def lista(
        self,
        telefono: str,
        texto: str,
        boton: str,
        filas: list[tuple[str, str, str]],
        *,
        texto_respaldo: str = '',
        agente: str = '',
    ) -> dict: ...

    def plantilla(self, telefono: str, nombre: str, variables: dict, *, agente: str = '') -> dict: ...


@dataclass(frozen=True)
class MetaSender:
    phone_id: str
    waba_id: str = ''
    canal: ClassVar[str] = 'meta'

    def _salida(self):
        from core.sandbox_canal import salida_por_phone_id

        return salida_por_phone_id(self.phone_id)

    def _con_outbox(self, telefono: str, correlacion: str, enviar):
        from core.models.outbox_envio import ejecutar

        return ejecutar(
            correlacion=correlacion,
            canal=self.canal,
            telefono=telefono,
            phone_id=self.phone_id,
            enviar=enviar,
        )

    def texto(
        self, telefono: str, texto: str, *, media_url: str | None = None, agente: str = '',
        correlacion: str = '',
    ) -> dict:
        from core.lineas.envio import enviar_meta

        def _enviar():
            with self._salida():
                return enviar_meta(telefono, texto, media_url=media_url, agente_evento=agente)

        return self._con_outbox(telefono, correlacion, _enviar)

    def botones(
        self, telefono: str, texto: str, botones: list[tuple[str, str]], *, agente: str = '',
        correlacion: str = '',
    ) -> dict:
        from core.lineas.envio import enviar_meta_botones

        def _enviar():
            with self._salida():
                return enviar_meta_botones(telefono, texto, botones, agente_evento=agente or 'sandbox_menu')

        return self._con_outbox(telefono, correlacion, _enviar)

    def lista(
        self,
        telefono: str,
        texto: str,
        boton: str,
        filas: list[tuple[str, str, str]],
        *,
        texto_respaldo: str = '',
        agente: str = '',
        correlacion: str = '',
    ) -> dict:
        from core.lineas.envio import enviar_meta_lista

        def _enviar():
            with self._salida():
                return enviar_meta_lista(
                    telefono,
                    texto,
                    boton,
                    filas,
                    texto_respaldo=texto_respaldo,
                    agente_evento=agente or 'sandbox_menu',
                )

        return self._con_outbox(telefono, correlacion, _enviar)

    def plantilla(
        self, telefono: str, nombre: str, variables: dict, *, agente: str = '',
        correlacion: str = '',
    ) -> dict:
        from core.lineas.envio import enviar_meta_plantilla

        def _enviar():
            with self._salida():
                return enviar_meta_plantilla(telefono, nombre, variables, agente_evento=agente or 'reenganche_drip')

        return self._con_outbox(telefono, correlacion, _enviar)

    def plantilla_imagen(
        self, telefono: str, nombre: str, media_url: str, variables: dict, *, agente: str = '',
        correlacion: str = '',
    ) -> dict:
        from core.lineas.envio import enviar_meta_plantilla_imagen

        def _enviar():
            with self._salida():
                return enviar_meta_plantilla_imagen(
                    telefono, nombre, media_url, variables, agente_evento=agente or 'diploma_meta'
                )

        return self._con_outbox(telefono, correlacion, _enviar)


@dataclass(frozen=True)
class TwilioSender:
    """Legado: demo y campañas HSM históricas. Sin botones ni listas nativas."""

    from_number: str = ''
    canal: ClassVar[str] = 'twilio'

    def texto(
        self, telefono: str, texto: str, *, media_url: str | None = None, agente: str = '',
        correlacion: str = '',
    ) -> dict:
        from core.models.outbox_envio import ejecutar
        from core.utils import enviar_whatsapp_twilio

        return ejecutar(
            correlacion=correlacion,
            canal=self.canal,
            telefono=telefono,
            phone_id='',
            enviar=lambda: enviar_whatsapp_twilio(
                telefono,
                texto,
                media_url=media_url,
                from_number=self.from_number or None,
                agente_evento=agente,
            ),
        )

    def botones(self, telefono: str, texto: str, botones: list[tuple[str, str]], *, agente: str = '') -> dict:
        opciones = '\n'.join(f'• {titulo}' for _id, titulo in botones)
        return self.texto(telefono, f'{texto}\n\n{opciones}'.strip(), agente=agente)

    def lista(
        self,
        telefono: str,
        texto: str,
        boton: str,
        filas: list[tuple[str, str, str]],
        *,
        texto_respaldo: str = '',
        agente: str = '',
    ) -> dict:
        if texto_respaldo:
            return self.texto(telefono, texto_respaldo, agente=agente)
        opciones = '\n'.join(f'• {titulo}' for _id, titulo, _desc in filas)
        return self.texto(telefono, f'{texto}\n\n{opciones}'.strip(), agente=agente)

    def plantilla(self, telefono: str, nombre: str, variables: dict, *, agente: str = '') -> dict:
        from core.whatsapp_service import enviar_template_twilio

        return enviar_template_twilio(telefono, nombre, variables)


def sender_de_linea(phone_id: str | None = None) -> Sender:
    """Sender de la línea de ese phone id. Sin phone id usa el de salida del turno."""
    if phone_id is None:
        from core.sandbox_canal import phone_id_de_salida

        phone_id = phone_id_de_salida()
    pnid = str(phone_id or '').strip()
    if not pnid:
        return TwilioSender()
    from core.lineas.campana import waba_de_linea

    return MetaSender(pnid, waba_de_linea(pnid))
