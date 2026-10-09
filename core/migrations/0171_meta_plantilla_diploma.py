# Plantilla de diploma en Meta, editable desde Configuración Global.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0170_experto_cafe_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionglobal',
            name='meta_plantilla_diploma',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Nombre de la plantilla aprobada en Meta (no es un HX de Twilio). '
                    'Encabezado: imagen. Cuerpo: {{1}} nombre, {{2}} curso, {{3}} código. '
                    'Vacío: el diploma se manda como imagen solo si la persona escribió en las últimas 24 horas. '
                    'Si META_TEMPLATE_DIPLOMA está en el entorno, ese valor gana.'
                ),
                max_length=128,
                verbose_name='Diploma — nombre de plantilla Meta',
            ),
        ),
    ]
