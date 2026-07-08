"""Crear o restablecer superusuario Django (admin eki)."""

import os
import secrets
import string

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


def _generar_password(longitud: int = 16) -> str:
    alfabeto = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))


class Command(BaseCommand):
    help = (
        'Crea o restablece un superusuario Django. '
        'En producción use: python manage.py crear_admin --reset --password "$ADMIN_BOOTSTRAP_PASSWORD"'
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin', help='Usuario Django (default: admin)')
        parser.add_argument('--email', default='admin@ekisolutions.com', help='Correo del superusuario')
        parser.add_argument(
            '--password',
            default='',
            help='Contraseña nueva. Si no se indica, usa ADMIN_BOOTSTRAP_PASSWORD o genera una aleatoria.',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Si el usuario existe, restablece contraseña y asegura is_staff + is_superuser.',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='Lista usuarios con acceso al admin (staff/superuser).',
        )

    def handle(self, *args, **options):
        if options['list']:
            self._listar_staff()
            return

        username = (options['username'] or 'admin').strip()
        email = (options['email'] or '').strip() or f'{username}@ekisolutions.com'
        password = (options['password'] or os.environ.get('ADMIN_BOOTSTRAP_PASSWORD') or '').strip()
        generada = False
        if not password:
            password = _generar_password()
            generada = True

        user = User.objects.filter(username=username).first()
        if user:
            if not options['reset']:
                self.stdout.write(
                    self.style.WARNING(
                        f'El usuario "{username}" ya existe. Use --reset para restablecer la contraseña.'
                    )
                )
                self.stdout.write(
                    f'  staff={user.is_staff} superuser={user.is_superuser} activo={user.is_active}'
                )
                return
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            if email:
                user.email = email
            user.save()
            accion = 'restablecido'
        else:
            User.objects.create_superuser(username, email, password)
            accion = 'creado'

        self.stdout.write(self.style.SUCCESS(f'Superusuario {accion}: {username}'))
        self.stdout.write(f'  Email: {email}')
        if generada:
            self.stdout.write(self.style.WARNING('  Contraseña temporal (cópiela ahora):'))
            self.stdout.write(f'  {password}')
            self.stdout.write('  Cambie la contraseña tras el primer ingreso al admin.')
        else:
            self.stdout.write('  Contraseña actualizada.')

    def _listar_staff(self):
        qs = User.objects.filter(is_staff=True).order_by('username')
        if not qs.exists():
            self.stdout.write(self.style.WARNING('No hay usuarios staff en la base de datos.'))
            return
        self.stdout.write('Usuarios con acceso al admin Django:')
        for u in qs:
            flags = []
            if u.is_superuser:
                flags.append('superuser')
            if not u.is_active:
                flags.append('INACTIVO')
            extra = f" ({', '.join(flags)})" if flags else ''
            self.stdout.write(f'  - {u.username} <{u.email}>{extra}')
