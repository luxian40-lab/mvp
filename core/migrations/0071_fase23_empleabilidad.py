from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0070_fase01_empleabilidad'),
    ]

    operations = [
        migrations.AddField(
            model_name='aliadoempleabilidad',
            name='cupos_disponibles',
            field=models.PositiveIntegerField(default=0, help_text='Vacantes disponibles para priorización del radar de empleabilidad.', verbose_name='Cupos disponibles'),
        ),
        migrations.AddField(
            model_name='aliadoempleabilidad',
            name='prioridad',
            field=models.PositiveSmallIntegerField(default=3, help_text='5 = máxima prioridad para aparecer en el radar de oportunidades.', verbose_name='Prioridad (1-5)'),
        ),
        migrations.AddField(
            model_name='aliadoempleabilidad',
            name='vigencia_desde',
            field=models.DateField(blank=True, help_text='Fecha de inicio de vigencia de la oportunidad.', null=True, verbose_name='Vigencia desde'),
        ),
        migrations.AddField(
            model_name='aliadoempleabilidad',
            name='vigencia_hasta',
            field=models.DateField(blank=True, help_text='Fecha de fin de vigencia de la oportunidad.', null=True, verbose_name='Vigencia hasta'),
        ),
        migrations.AddField(
            model_name='misionempleabilidad',
            name='canal_origen',
            field=models.CharField(default='whatsapp', max_length=40, verbose_name='Canal origen'),
        ),
        migrations.AddField(
            model_name='misionempleabilidad',
            name='estado_flujo',
            field=models.CharField(choices=[('descubierto', 'Descubierto'), ('interesado', 'Interesado'), ('postulado', 'Postulado'), ('entrevista', 'Entrevista'), ('vinculado', 'Vinculado'), ('descartado', 'Descartado')], default='descubierto', max_length=20, verbose_name='Estado del embudo'),
        ),
        migrations.AddField(
            model_name='misionempleabilidad',
            name='fecha_entrevista',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='misionempleabilidad',
            name='fecha_interes',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='misionempleabilidad',
            name='fecha_postulacion',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='misionempleabilidad',
            name='fecha_vinculacion',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='misionempleabilidad',
            name='puntaje_prioridad',
            field=models.FloatField(default=0, help_text='Score calculado para priorizar oportunidades en el radar.', verbose_name='Puntaje de priorización'),
        ),
        migrations.AddIndex(
            model_name='misionempleabilidad',
            index=models.Index(fields=['cliente', 'estado_flujo', 'fecha_descubierta'], name='core_misione_cliente_9f4f77_idx'),
        ),
    ]
