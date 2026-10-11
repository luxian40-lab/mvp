"""Lista inscripciones que no cumplen la regla de cursos. No escribe."""
from django.core.management.base import BaseCommand

from core.cursos_permitidos import inscripcion_fuera_de_regla
from core.models import ProgresoEstudiante


class Command(BaseCommand):
    help = (
        'Lista estudiantes con un curso que no es de su organización ni general de eki. '
        'No modifica nada.'
    )

    def handle(self, *args, **options):
        total = 0
        qs = (
            ProgresoEstudiante.objects.select_related('estudiante', 'estudiante__cliente', 'curso', 'curso__cliente')
            .order_by('estudiante_id', 'curso_id')
        )
        for progreso in qs.iterator():
            if not inscripcion_fuera_de_regla(progreso):
                continue
            total += 1
            est = progreso.estudiante
            org = est.cliente.nombre if est.cliente_id else 'Sin organización'
            self.stdout.write(
                f'estudiante_id={est.pk} cedula={est.cedula} nombre={est.nombre} '
                f'curso_id={progreso.curso_id} curso={progreso.curso.nombre} organizacion={org}'
            )
        self.stdout.write(f'total={total}')
