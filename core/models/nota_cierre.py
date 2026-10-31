"""Nota de 1 a 10 al cerrar un curso en la línea principal."""
from django.db import models


class NotaCierreCurso(models.Model):
    estudiante = models.ForeignKey(
        'core.Estudiante',
        on_delete=models.CASCADE,
        related_name='notas_cierre_curso',
    )
    curso = models.ForeignKey(
        'core.Curso',
        on_delete=models.CASCADE,
        related_name='notas_cierre',
    )
    nota = models.PositiveSmallIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['estudiante', 'curso'],
                name='nota_cierre_est_curso',
            ),
        ]
        verbose_name = 'Nota de cierre del curso'
        verbose_name_plural = 'Notas de cierre del curso'

    def __str__(self):
        return f'{self.estudiante_id} · {self.curso_id} · {self.nota}'
