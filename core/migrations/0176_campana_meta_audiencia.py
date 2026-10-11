from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0175_plantilla_meta_importacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='campanameta',
            name='dias_repeticion',
            field=models.PositiveSmallIntegerField(
                default=14,
                help_text='No se vuelve a escribir a quien recibió esta plantilla hace menos de estos días. 14 es el valor inicial.',
                verbose_name='Días entre envíos de la misma plantilla',
            ),
        ),
        migrations.AddField(
            model_name='campanameta',
            name='reglas_variables',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Por cada {{n}}: origen, qué hacer si falta el dato y el texto de respaldo.',
                verbose_name='Reglas de variables',
            ),
        ),
        migrations.AddField(
            model_name='campanameta',
            name='grupos',
            field=models.ManyToManyField(
                blank=True,
                related_name='campanas_meta_grupos',
                to='core.grupoestudiantes',
                verbose_name='Grupos',
            ),
        ),
    ]
