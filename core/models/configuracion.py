"""Modelos de configuracion (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models


class ConfiguracionGlobal(models.Model):
    """Singleton de configuración general de eki, editable desde el admin.

    Solo debe existir una fila (id=1). El método `get_solo()` la crea si falta.
    """
    content_sid_habeas_data_global = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Habeas Data — Plantilla Twilio general (Content SID)',
        help_text=(
            'Content SID (HX...) de la plantilla Twilio aprobada para el Habeas Data por defecto. '
            'Se usa cuando el cliente no tiene su propio Content SID configurado.'
        ),
    )
    meta_plantilla_diploma = models.CharField(
        max_length=128,
        blank=True,
        default='',
        verbose_name='Diploma — nombre de plantilla Meta',
        help_text=(
            'Nombre de la plantilla aprobada en Meta (no es un HX de Twilio). '
            'Encabezado: imagen. Cuerpo: {{1}} nombre, {{2}} curso, {{3}} código. '
            'Vacío: el diploma se manda como imagen solo si la persona escribió en las últimas 24 horas. '
            'Si META_TEMPLATE_DIPLOMA está en el entorno, ese valor gana.'
        ),
    )
    cursos_linea_2 = models.ManyToManyField(
        'Curso',
        blank=True,
        related_name='en_linea_2',
        verbose_name='Cursos de la línea 2 (opcional)',
        help_text=(
            'La línea 2 no abre carrusel. El curso entra por campaña o inscripción. '
            'Esta lista es opcional para campañas futuras; no cambia el menú de WhatsApp.'
        ),
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        verbose_name = 'Configuración Global'
        verbose_name_plural = 'Configuración Global'

    def __str__(self):
        return 'Configuración Global eki'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
