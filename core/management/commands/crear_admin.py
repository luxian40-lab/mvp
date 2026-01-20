from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea un superusuario por defecto para el ambiente de producción'

    def handle(self, *args, **options):
        username = 'admin'
        email = 'admin@ekisolutions.com'
        password = 'Eki@Admin2025'

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'✓ El usuario "{username}" ya existe')
            )
        else:
            User.objects.create_superuser(username, email, password)
            self.stdout.write(
                self.style.SUCCESS(f'✓ Superusuario creado exitosamente')
            )
            self.stdout.write(f'  Usuario: {username}')
            self.stdout.write(f'  Email: {email}')
            self.stdout.write(f'  Contraseña: {password}')
