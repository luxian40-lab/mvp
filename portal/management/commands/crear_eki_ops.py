"""Crear o actualizar usuario portal con rol eki_ops (semi-admin app)."""

import os
import secrets
import string

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.models import Cliente
from portal.models import PortalUsuario


def _generar_password(longitud: int = 14) -> str:
    alfabeto = string.ascii_letters + string.digits + '!@#$'
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))


class Command(BaseCommand):
    help = (
        'Crea usuario portal rol=eki_ops (métricas + editor cursos en /portal/ops/). '
        'No es superusuario Django.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', default='eki_ops')
        parser.add_argument('--email', default='ops@eki.technology')
        parser.add_argument(
            '--password',
            default='',
            help='Si vacío: EKI_OPS_PASSWORD env o genera una temporal.',
        )
        parser.add_argument(
            '--org',
            default='',
            help='Nombre (o id) de la org home. Default: Agronexo o primera activa.',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Si el usuario existe, actualiza password y rol eki_ops.',
        )

    def handle(self, *args, **options):
        username = (options['username'] or 'eki_ops').strip()
        email = (options['email'] or f'{username}@eki.technology').strip()
        password = (options['password'] or os.environ.get('EKI_OPS_PASSWORD') or '').strip()
        generada = False
        if not password:
            password = _generar_password()
            generada = True

        org = self._resolver_org(options.get('org') or '')
        if not org:
            raise CommandError(
                'No hay organización activa. Cree un Cliente o pase --org "Agronexo".'
            )

        user = User.objects.filter(username=username).first()
        if user and not options['reset']:
            pu = getattr(user, 'portal_usuario', None)
            self.stdout.write(self.style.WARNING(
                f'Usuario "{username}" ya existe '
                f'(rol={getattr(pu, "rol", "?")}, org={getattr(pu, "organizacion", None)}). '
                'Use --reset para actualizar.'
            ))
            return

        if not user:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.is_staff = False
            user.is_superuser = False
            user.is_active = True
            user.save()
            accion = 'creado'
        else:
            user.set_password(password)
            user.email = email
            user.is_staff = False
            user.is_superuser = False
            user.is_active = True
            user.save()
            accion = 'actualizado'

        PortalUsuario.objects.update_or_create(
            user=user,
            defaults={
                'organizacion': org,
                'rol': 'eki_ops',
                'debe_cambiar_credenciales': False,
            },
        )

        self.stdout.write(self.style.SUCCESS(
            f'eki_ops {accion}: {username} → org={org.nombre} (id={org.pk})'
        ))
        self.stdout.write('  Login: https://app.eki.technology/portal/login/ → /portal/ops/')
        if generada:
            self.stdout.write(self.style.WARNING('  Contraseña temporal (cópiela ahora):'))
            self.stdout.write(f'  {password}')
        else:
            self.stdout.write('  Contraseña establecida.')

    def _resolver_org(self, raw: str) -> Cliente | None:
        raw = (raw or '').strip()
        if raw.isdigit():
            return Cliente.objects.filter(pk=int(raw), activo=True).first()
        if raw:
            return (
                Cliente.objects.filter(nombre__icontains=raw, activo=True)
                .order_by('id')
                .first()
            )
        agro = Cliente.objects.filter(nombre__icontains='Agronexo', activo=True).first()
        if agro:
            return agro
        return Cliente.objects.filter(activo=True).order_by('id').first()
