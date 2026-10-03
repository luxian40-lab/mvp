"""Reencola un WebhookFallido. No borra la fila: el staff conserva el registro.

Las tres tareas entran: el sobre guarda el nombre corto y, en Nat, forzar_canal.
Meta y Twilio educativo no llevan kwargs.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


_TAREAS = (
    'procesar_sandbox_meta_async',
    'procesar_twilio_webhook_async',
    'procesar_bot_comercial_webhook_async',
)
_VENTANA = timedelta(hours=24)


class Command(BaseCommand):
    help = (
        'Muestra antigüedad y texto, y reencola el webhook fallido. '
        'Uso: reprocesar_webhook_fallido <id> --confirmar'
    )

    def add_arguments(self, parser):
        parser.add_argument('id', type=int)
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Sin esto el comando solo muestra el mensaje y no reencola.',
        )
        parser.add_argument(
            '--forzar',
            action='store_true',
            help='Reencola aunque el fallo tenga más de 24 h.',
        )

    def handle(self, *args, **options):
        from core.tasks import (
            procesar_bot_comercial_webhook_async,
            procesar_sandbox_meta_async,
            procesar_twilio_webhook_async,
        )
        from core.webhook_evento import WebhookFallido

        permitidas = {
            'procesar_sandbox_meta_async': procesar_sandbox_meta_async,
            'procesar_twilio_webhook_async': procesar_twilio_webhook_async,
            'procesar_bot_comercial_webhook_async': procesar_bot_comercial_webhook_async,
        }
        try:
            fila = WebhookFallido.objects.get(pk=options['id'])
        except WebhookFallido.DoesNotExist as exc:
            raise CommandError(f'No existe WebhookFallido id={options["id"]}') from exc

        sobre = fila.payload if isinstance(fila.payload, dict) else {}
        nombre = str(sobre.get('tarea') or '')
        corto = nombre.rsplit('.', 1)[-1]
        datos = sobre.get('datos') if isinstance(sobre.get('datos'), dict) else {}
        texto = str(datos.get('Body') or '')[:300]
        edad = timezone.now() - fila.creado
        self.stdout.write(
            f'id={fila.pk} canal={fila.canal} external_id={fila.external_id} '
            f'antiguedad={edad} texto={texto!r}'
        )
        if corto not in _TAREAS:
            raise CommandError(f'Tarea no permitida: {nombre or "(vacía)"}')
        if not options['confirmar']:
            raise CommandError('Falta --confirmar. No se reencoló.')
        if edad > _VENTANA and not options['forzar']:
            raise CommandError('Pasaron más de 24 h. Repite con --forzar --confirmar.')
        from core.locks import borrar_entrega

        borrar_entrega(fila.canal, fila.external_id)
        kwargs = sobre.get('kwargs') if isinstance(sobre.get('kwargs'), dict) else {}
        if corto != 'procesar_bot_comercial_webhook_async':
            kwargs = {}
        else:
            kwargs = {'forzar_canal': bool(kwargs.get('forzar_canal'))}
        async_result = permitidas[corto].delay(datos, **kwargs)
        self.stdout.write(
            f'reencolado id={fila.pk} canal={fila.canal} external_id={fila.external_id} task={async_result.id}'
        )
