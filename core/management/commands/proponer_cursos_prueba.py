"""Lista cursos cuyo nombre parece de prueba. No cambia activo ni nada más."""
from django.core.management.base import BaseCommand

from core.cursos_permitidos import parece_nombre_de_prueba
from core.models import Curso


class Command(BaseCommand):
    help = (
        'Lista cursos con nombre de prueba (Nuevo curso 5–14, Curso Test, [PRUEBA], pruebas). '
        'No los marca ni los oculta. Para ocultar uno, desactívelo cuando lo confirme.'
    )

    def handle(self, *args, **options):
        total = 0
        for curso in Curso.objects.select_related('cliente').order_by('id'):
            if not parece_nombre_de_prueba(curso.nombre):
                continue
            total += 1
            org = curso.cliente.nombre if curso.cliente_id else 'General'
            estado = 'activo' if curso.activo else 'inactivo'
            self.stdout.write(
                f'curso_id={curso.pk} nombre={curso.nombre} organizacion={org} {estado}'
            )
        self.stdout.write(f'total={total}')
