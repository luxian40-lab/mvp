from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0209_progresoestudiante_origen_cierre'),
    ]

    operations = [
        migrations.AlterField(
            model_name='certificado',
            name='calificacion_final',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Calificación final (0-100). Vacía si el curso no tuvo preguntas (flag corte 5).',
                max_digits=5,
                null=True,
            ),
        ),
    ]
