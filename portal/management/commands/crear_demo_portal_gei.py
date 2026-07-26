"""Crea org + usuario portal GEI con sandbox de 10 cupos para QA."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Cliente, Curso, Modulo
from portal.capabilities import modulos_portal, portal_home_url
from portal.gei_sandbox import GEI_SANDBOX_CUPOS_DEFAULT, asegurar_cupos_sandbox
from portal.models import PortalUsuario


class Command(BaseCommand):
    help = 'Crea cliente portal GEI + usuario demo + 10 cupos sandbox.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='demo_gei')
        parser.add_argument('--password', default='GeiDemo2026!')
        parser.add_argument('--email', default='demo.gei@eki.local')
        parser.add_argument('--org', default='Demo Fichas GEI')
        parser.add_argument('--cupos', type=int, default=GEI_SANDBOX_CUPOS_DEFAULT)

    @transaction.atomic
    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        org_name = options['org']
        cupos = options['cupos']

        from datetime import date

        org, created_org = Cliente.objects.get_or_create(
            email=email,
            defaults={
                'nombre': org_name,
                'contacto_principal': 'Demo GEI',
                'telefono': '573001000888',
                'activo': True,
                'tipo_proyecto': 'gei',
                'portal_productos': 'gei',
                'fecha_fin_suscripcion': date(2099, 12, 31),
            },
        )
        if not created_org:
            org.nombre = org_name
            org.tipo_proyecto = 'gei'
            org.portal_productos = 'gei'
            org.activo = True
            if not org.fecha_fin_suscripcion or org.fecha_fin_suscripcion < date.today():
                org.fecha_fin_suscripcion = date(2099, 12, 31)
            org.save(update_fields=[
                'nombre', 'tipo_proyecto', 'portal_productos', 'activo', 'fecha_fin_suscripcion',
            ])

        curso, _ = Curso.objects.get_or_create(
            cliente=org,
            nombre='Curso Demo Inventario GEI',
            defaults={
                'descripcion': 'Curso de prueba para fichas GEI y sandbox portal.',
                'activo': True,
                'tiene_formulario_gei': True,
                'orden': 1,
            },
        )
        if not curso.tiene_formulario_gei:
            curso.tiene_formulario_gei = True
            curso.activo = True
            curso.save(update_fields=['tiene_formulario_gei', 'activo'])

        for num, titulo in ((4, 'Contexto finca'), (5, 'Balance GEI')):
            Modulo.objects.get_or_create(
                curso=curso,
                numero=num,
                defaults={
                    'titulo': titulo,
                    'descripcion': f'Módulo {num}: {titulo} (demo GEI).',
                    'contenido': '',
                },
            )

        # Flujos GEI (si el comando de carga existe)
        try:
            from django.core.management import call_command
            m4 = Modulo.objects.get(curso=curso, numero=4)
            m5 = Modulo.objects.get(curso=curso, numero=5)
            call_command(
                'cargar_flujo_gei', curso.id, m4.id,
                bloque='contexto', cliente_id=org.id, reset=True, verbosity=0,
            )
            call_command(
                'cargar_flujo_gei', curso.id, m5.id,
                bloque='balance', cliente_id=org.id, reset=True, verbosity=0,
            )
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'Flujos GEI no cargados: {exc}'))

        user, created_user = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'is_staff': False, 'is_superuser': False},
        )
        user.set_password(password)
        user.email = email
        user.is_active = True
        user.save()

        pu, _ = PortalUsuario.objects.update_or_create(
            user=user,
            defaults={
                'organizacion': org,
                'rol': 'admin',
                'debe_cambiar_credenciales': False,
                'password_temporal': '',
            },
        )

        slots = asegurar_cupos_sandbox(org, cupos=cupos, curso=curso)
        mods = modulos_portal(org)

        self.stdout.write(self.style.SUCCESS(
            f"Org id={org.pk} created={created_org} mods={mods} home={portal_home_url(org)}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Curso id={curso.id} sandbox_cupos={len(slots)}"
        ))
        self.stdout.write(
            f"Login portal: username={username} password={password} "
            f"(portal_usuario id={pu.pk}, user_created={created_user})"
        )
        self.stdout.write('Sandbox: /portal/gei/sandbox/  ·  Excel: /portal/gei/exportar/')
