# -*- coding: utf-8 -*-
"""Provisiona enlaces margen + acceso portal para cliente piloto."""
import secrets

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from calculadora_margen.analytics import resumen_uso_cliente
from calculadora_margen.links import obtener_o_crear_enlace, urls_margen_cliente


class Command(BaseCommand):
    help = 'Cliente piloto: enlaces margen.eki.technology + portal /portal/margen/ + KPIs'

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True)
        parser.add_argument('--curso-id', type=int, default=None, help='Curso WA para ?curso=')
        parser.add_argument('--dias', type=int, default=30)
        parser.add_argument('--crear-portal', action='store_true', help='Crea usuario portal admin si no existe')
        parser.add_argument('--portal-username', type=str, default='')
        parser.add_argument('--portal-email', type=str, default='')
        parser.add_argument('--portal-password', type=str, default='')

    @transaction.atomic
    def handle(self, *args, **options):
        from core.models import Cliente, Curso
        from portal.models import PortalUsuario

        cliente = Cliente.objects.filter(pk=options['cliente_id']).first()
        if not cliente:
            self.stderr.write(self.style.ERROR(f'Cliente {options["cliente_id"]} no existe'))
            raise SystemExit(1)

        curso_id = options.get('curso_id')
        curso = Curso.objects.filter(pk=curso_id).first() if curso_id else None

        enlace = obtener_o_crear_enlace(cliente)
        urls = urls_margen_cliente(cliente, curso_id=curso_id)
        stats = resumen_uso_cliente(cliente.pk, dias=options['dias'])

        self.stdout.write(self.style.SUCCESS(f'Cliente: {cliente.nombre} (id={cliente.pk})'))
        if curso:
            self.stdout.write(f'Curso: {curso.nombre} (id={curso.pk})')

        self.stdout.write('\n--- Calculadora (estudiante / WA) ---')
        self.stdout.write(f'  Org:   {urls["url_org"]}')
        self.stdout.write(f'  Token: {urls["url_token"]}')

        self.stdout.write('\n--- Portal B2B (métricas agregadas) ---')
        self.stdout.write('  https://eki.technology/portal/margen/')

        portal_creds = None
        if options.get('crear_portal'):
            slug = (cliente.nombre or 'piloto').lower().replace(' ', '_')[:24]
            username = (options.get('portal_username') or '').strip() or f'margen_{cliente.pk}'
            email = (options.get('portal_email') or '').strip() or cliente.email or f'{username}@eki.local'
            password = (options.get('portal_password') or '').strip() or secrets.token_urlsafe(10)[:14]

            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'is_staff': False, 'is_superuser': False},
            )
            user.email = email
            user.is_active = True
            user.set_password(password)
            user.save()

            pu, _ = PortalUsuario.objects.update_or_create(
                user=user,
                defaults={
                    'organizacion': cliente,
                    'rol': 'admin',
                    'debe_cambiar_credenciales': False,
                    'password_temporal': password,
                },
            )
            portal_creds = (username, password, created, pu.pk)

        usuarios = PortalUsuario.objects.filter(organizacion_id=cliente.pk)
        if usuarios.exists():
            self.stdout.write('\n--- Usuarios portal ---')
            for u in usuarios[:5]:
                email = u.user.email or u.user.username
                self.stdout.write(f'  {email} — rol {u.rol}')
        elif not portal_creds:
            self.stdout.write(self.style.WARNING(
                '\nSin PortalUsuario. Usa --crear-portal o admin Cliente → inline Portal.'
            ))

        if portal_creds:
            username, password, created, pu_id = portal_creds
            self.stdout.write(self.style.SUCCESS(
                f'\nPortal creado: user={username} pass={password} '
                f'(nuevo={created}, portal_usuario id={pu_id})'
            ))
            self.stdout.write('  Login: https://eki.technology/portal/login/')

        self.stdout.write('\n--- Telemetría (últimos %d días, sin montos PII) ---' % options['dias'])
        self.stdout.write(f'  Sesiones: {stats["sesiones"]}')
        self.stdout.write(f'  Aperturas: {stats["aperturas"]}')
        self.stdout.write(f'  Cálculos completos: {stats["calculos"]}')
        self.stdout.write(f'  Tasa completa: {stats["tasa_completa_pct"]}%')
        self.stdout.write(f'  Simulaciones precio: {stats["simulaciones"]}')
        self.stdout.write(f'  Recomendaciones IA: {stats["recomendaciones"]}')
        if stats.get('margen_rangos'):
            self.stdout.write(f'  Rangos margen: {stats["margen_rangos"]}')

        self.stdout.write(f'\nSlug: {enlace.slug} | Token: {enlace.token[:8]}…')
