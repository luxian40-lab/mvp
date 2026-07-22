"""Crea (o actualiza) una org + usuario portal solo-Nat para QA."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Cliente
from portal.capabilities import modulos_portal, portal_home_url, portal_solo_nat
from portal.models import PortalUsuario


class Command(BaseCommand):
    help = 'Crea cliente portal_productos=nat y usuario demo para revisar el hub sin cursos.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='demo_nat')
        parser.add_argument('--password', default='NatDemo2026!')
        parser.add_argument('--email', default='demo.nat@eki.local')
        parser.add_argument('--org', default='Demo Solo Nat')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        org_name = options['org']

        org, created_org = Cliente.objects.get_or_create(
            email=email,
            defaults={
                'nombre': org_name,
                'contacto_principal': 'Demo Nat',
                'telefono': '573001000777',
                'activo': True,
                'tipo_proyecto': 'nat',
                'portal_productos': 'nat',
            },
        )
        if not created_org:
            org.nombre = org_name
            org.tipo_proyecto = 'nat'
            org.portal_productos = 'nat'
            org.activo = True
            org.save(update_fields=['nombre', 'tipo_proyecto', 'portal_productos', 'activo'])

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
            defaults={'organizacion': org, 'rol': 'admin'},
        )

        mods = modulos_portal(org)
        self.stdout.write(self.style.SUCCESS(
            f"Org id={org.pk} solo_nat={portal_solo_nat(org)} mods={mods} home={portal_home_url(org)}"
        ))
        self.stdout.write(
            f"Login portal: username={username} password={password} "
            f"(org={org.nombre}, portal_usuario id={pu.pk}, user_created={created_user})"
        )
