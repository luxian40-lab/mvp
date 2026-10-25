"""Cuántos estudiantes hay en cada estado del motor. Solo lee.

Fase A del plan de modularidad: antes de borrar ramas del cuerpo (D4) hay que
saber si alguien sigue en los estados legado.

    python manage.py contar_estados_motor
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

LEGADO = (
    'esperando_respuesta_tutor_ia',
    'esperando_respuesta_progreso',
    'esperando_respuesta_recuperacion',
)


class Command(BaseCommand):
    help = 'Cuenta estudiantes por estado_onboarding y estado_chat (solo lectura).'

    def handle(self, *args, **options):
        from core.models import Estudiante

        filas = (
            Estudiante.objects.values('estado_onboarding')
            .annotate(n=Count('id'))
            .order_by('-n', 'estado_onboarding')
        )
        self.stdout.write('estado_onboarding')
        conteo = {}
        for fila in filas:
            estado = fila['estado_onboarding'] or '(vacío)'
            conteo[estado] = fila['n']
            self.stdout.write(f'  {estado}: {fila["n"]}')
        self.stdout.write('legado (D4 solo borra si están en 0)')
        for estado in LEGADO:
            self.stdout.write(f'  {estado}: {conteo.get(estado, 0)}')
        self.stdout.write('estado_chat')
        for fila in Estudiante.objects.values('estado_chat').annotate(n=Count('id')).order_by('-n', 'estado_chat'):
            self.stdout.write(f'  {fila["estado_chat"] or "(vacío)"}: {fila["n"]}')
