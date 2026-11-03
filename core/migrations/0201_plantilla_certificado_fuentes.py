from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0200_recordatorio_curso_maximo_envios'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantillacertificado',
            name='fuente_cedula',
            field=models.PositiveSmallIntegerField(
                default=33,
                help_text='Cédula / documento sobre el marcador rojo. Por defecto 33.',
                verbose_name='Tamaño documento (px)',
            ),
        ),
        migrations.AddField(
            model_name='plantillacertificado',
            name='fuente_fecha',
            field=models.PositiveSmallIntegerField(
                default=29,
                help_text='Fecha sobre el marcador amarillo. Por defecto 29.',
                verbose_name='Tamaño fecha (px)',
            ),
        ),
        migrations.AddField(
            model_name='plantillacertificado',
            name='fuente_nombre',
            field=models.PositiveSmallIntegerField(
                default=56,
                help_text='Texto del nombre sobre el marcador gris. Por defecto 56.',
                verbose_name='Tamaño nombre (px)',
            ),
        ),
    ]
