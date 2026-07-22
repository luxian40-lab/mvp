"""Diagnóstico operativo Nat por organización."""

from django.core.management.base import BaseCommand, CommandError

from core.bot_comercial_routing import es_destino_bot_comercial, numeros_destino_comercial
from core.models import Cliente
from portal.nat_service import checklist_preparacion_nat


class Command(BaseCommand):
    help = 'Muestra checklist Nat y si el número de la org entra al canal comercial.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True, help='ID de Cliente')

    def handle(self, *args, **options):
        cid = options['cliente']
        org = Cliente.objects.filter(pk=cid).first()
        if not org:
            raise CommandError(f'Cliente id={cid} no encontrado')

        self.stdout.write(self.style.NOTICE(f'Nat — {org.nombre} (id={org.pk})'))
        linea = (org.numero_whatsapp_nat or '').strip()
        self.stdout.write(f'  numero_whatsapp_nat: {linea or "(vacío)"}')
        if linea:
            ok_route = es_destino_bot_comercial(linea)
            self.stdout.write(
                f'  enruta a comercial: {"sí" if ok_route else "NO"}'
            )
        self.stdout.write(f'  destinos comerciales conocidos: {len(numeros_destino_comercial())}')

        for item in checklist_preparacion_nat(org):
            flag = 'OK' if item['ok'] else item['nivel'].upper()
            self.stdout.write(f'  [{flag}] {item["titulo"]}: {item["detalle"]}')
