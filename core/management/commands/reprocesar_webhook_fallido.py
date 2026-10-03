"""Reencola un WebhookFallido. No borra la fila: el staff conserva el registro."""
from django.core.management.base import BaseCommand, CommandError


_TAREAS = (
    'procesar_sandbox_meta_async',
    'procesar_twilio_webhook_async',
    'procesar_bot_comercial_webhook_async',
)


class Command(BaseCommand):
    help = 'Reencola el webhook fallido indicado. Uso: reprocesar_webhook_fallido <id>'

    def add_arguments(self, parser):
        parser.add_argument('id', type=int)

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
        if corto not in _TAREAS:
            raise CommandError(f'Tarea no permitida: {nombre or "(vacía)"}')
        datos = sobre.get('datos') if isinstance(sobre.get('datos'), dict) else {}
        kwargs = sobre.get('kwargs') if isinstance(sobre.get('kwargs'), dict) else {}
        if corto != 'procesar_bot_comercial_webhook_async':
            kwargs = {}
        else:
            kwargs = {'forzar_canal': bool(kwargs.get('forzar_canal'))}
        async_result = permitidas[corto].delay(datos, **kwargs)
        self.stdout.write(
            f'reencolado id={fila.pk} canal={fila.canal} external_id={fila.external_id} task={async_result.id}'
        )
