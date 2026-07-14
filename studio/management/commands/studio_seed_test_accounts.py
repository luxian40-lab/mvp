"""Crea cuentas de prueba Solo-Studio (creador + estudiante). Idempotente."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from studio.cuenta_service import registrar_cuenta_aula
from studio.models import CreadorStudio, CuentaAula

CREADOR_EMAIL = 'creador.test@eki.studio'
ESTUDIANTE_EMAIL = 'alumno.test@eki.studio'
PASSWORD = 'StudioTest2026!'


class Command(BaseCommand):
    help = 'Crea creador y alumno de prueba en Studio (no toca admin ni B2B aula).'

    def handle(self, *args, **options):
        creador = self._ensure_creador()
        alumno = self._ensure_alumno()
        self.stdout.write(self.style.SUCCESS('Cuentas Studio listas para pruebas:'))
        self.stdout.write('')
        self.stdout.write('  Creador (profesor Studio)')
        self.stdout.write(f'    URL: /studio/cuenta/login/  o  /studio/creador/panel/')
        self.stdout.write(f'    Correo: {CREADOR_EMAIL}')
        self.stdout.write(f'    Clave:  {PASSWORD}')
        self.stdout.write(f'    Perfil: {creador.nombre_publico} (activo={creador.activo})')
        self.stdout.write('')
        self.stdout.write('  Alumno (cuenta Studio)')
        self.stdout.write(f'    URL: /studio/cuenta/login/')
        self.stdout.write(f'    Correo: {ESTUDIANTE_EMAIL}')
        self.stdout.write(f'    Clave:  {PASSWORD}')
        self.stdout.write(f'    CuentaAula id={alumno.pk}')
        self.stdout.write('')
        self.stdout.write(
            self.style.WARNING(
                'Abrí Studio en ventana privada (o distinto navegador) si estás en /admin/.'
            )
        )

    def _ensure_creador(self) -> CreadorStudio:
        existing = CreadorStudio.objects.filter(user__username=CREADOR_EMAIL).select_related('user').first()
        if existing:
            user = existing.user
            user.set_password(PASSWORD)
            user.save(update_fields=['password'])
            if not existing.activo:
                existing.activo = True
                existing.save(update_fields=['activo'])
            self.stdout.write(f'Reutilizado creador: {CREADOR_EMAIL}')
            return existing

        cuenta = CuentaAula.objects.filter(user__username=CREADOR_EMAIL).select_related('user').first()
        if not cuenta:
            cuenta, err = registrar_cuenta_aula(
                email=CREADOR_EMAIL,
                password=PASSWORD,
                nombre='Creador Test Studio',
            )
            if err or not cuenta:
                raise SystemExit(err or 'No se pudo crear cuenta creador')
        else:
            cuenta.user.set_password(PASSWORD)
            cuenta.user.save(update_fields=['password'])

        creador, _ = CreadorStudio.objects.get_or_create(
            user=cuenta.user,
            defaults={
                'nombre_publico': 'Creador Test Studio',
                'bio': 'Cuenta de prueba Studio',
                'activo': True,
            },
        )
        if not creador.activo:
            creador.activo = True
            creador.save(update_fields=['activo'])
        self.stdout.write(f'Creado creador: {CREADOR_EMAIL}')
        return creador

    def _ensure_alumno(self) -> CuentaAula:
        cuenta = CuentaAula.objects.filter(user__username=ESTUDIANTE_EMAIL).select_related('user').first()
        if cuenta:
            cuenta.user.set_password(PASSWORD)
            cuenta.user.save(update_fields=['password'])
            self.stdout.write(f'Reutilizado alumno: {ESTUDIANTE_EMAIL}')
            return cuenta

        cuenta, err = registrar_cuenta_aula(
            email=ESTUDIANTE_EMAIL,
            password=PASSWORD,
            nombre='Alumno Test Studio',
        )
        if err or not cuenta:
            raise SystemExit(err or 'No se pudo crear cuenta alumno')
        # No crear CreadorStudio: es solo estudiante marketplace
        self.stdout.write(f'Creado alumno: {ESTUDIANTE_EMAIL}')
        return cuenta
