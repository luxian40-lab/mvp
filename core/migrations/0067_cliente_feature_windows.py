from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0066_drip_geogam_open_questions'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='fecha_fin_gamificacion_proximidad',
            field=models.DateField(blank=True, help_text='Fecha límite de activación del radar de proximidad para este cliente.', null=True, verbose_name='Fin Gamificación Proximidad'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='fecha_fin_pregunta_abierta_final',
            field=models.DateField(blank=True, help_text='Fecha límite de activación de la pregunta abierta final para este cliente.', null=True, verbose_name='Fin Pregunta Abierta Final'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='fecha_inicio_gamificacion_proximidad',
            field=models.DateField(blank=True, help_text='Fecha desde la cual se activa el radar de proximidad para este cliente.', null=True, verbose_name='Inicio Gamificación Proximidad'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='fecha_inicio_pregunta_abierta_final',
            field=models.DateField(blank=True, help_text='Fecha desde la cual se activa la pregunta abierta final para este cliente.', null=True, verbose_name='Inicio Pregunta Abierta Final'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='habilitar_gamificacion_proximidad',
            field=models.BooleanField(default=False, help_text='Activa radar de empleabilidad por proximidad para este cliente según la ventana de fechas.', verbose_name='Habilitar Gamificación por Proximidad'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='habilitar_pregunta_abierta_final',
            field=models.BooleanField(default=False, help_text='Activa la pregunta abierta final para este cliente según la ventana de fechas.', verbose_name='Habilitar Pregunta Abierta Final'),
        ),
    ]
