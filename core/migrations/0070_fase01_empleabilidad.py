from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0069_documentoragcomercial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='empleabilidad_cooldown_horas',
            field=models.PositiveIntegerField(default=24, help_text='Horas mínimas entre validaciones exitosas de empleabilidad por estudiante.', verbose_name='Cooldown entre validaciones (horas)'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='empleabilidad_exploracion_activa',
            field=models.BooleanField(default=False, help_text='Activa la experiencia tipo exploración para oportunidades cercanas (por cliente).', verbose_name='Empleabilidad Exploración Activa'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='empleabilidad_max_misiones_dia',
            field=models.PositiveIntegerField(default=3, help_text='Límite diario de misiones de exploración por estudiante.', verbose_name='Máximo misiones por día'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='empleabilidad_puntos_validacion',
            field=models.PositiveIntegerField(default=30, help_text='Puntos de gamificación otorgados al validar un código de oportunidad.', verbose_name='Puntos por validación'),
        ),
        migrations.AddField(
            model_name='cliente',
            name='empleabilidad_radio_metros',
            field=models.PositiveIntegerField(default=800, help_text='Distancia máxima para detectar oportunidades cercanas.', verbose_name='Radio de búsqueda (metros)'),
        ),
        migrations.CreateModel(
            name='MisionEmpleabilidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[('descubierta', 'Descubierta'), ('reclamada', 'Reclamada'), ('completada', 'Completada'), ('cancelada', 'Cancelada')], default='descubierta', max_length=20, verbose_name='Estado')),
                ('latitud', models.FloatField(blank=True, null=True, verbose_name='Latitud referencia')),
                ('longitud', models.FloatField(blank=True, null=True, verbose_name='Longitud referencia')),
                ('distancia_metros', models.FloatField(blank=True, null=True, verbose_name='Distancia en metros')),
                ('codigo_validado', models.BooleanField(default=False, verbose_name='Código validado')),
                ('puntos_otorgados', models.IntegerField(default=0, verbose_name='Puntos otorgados')),
                ('metadata', models.JSONField(blank=True, help_text='Datos adicionales de misión (debug/contexto).', null=True)),
                ('fecha_descubierta', models.DateTimeField(auto_now_add=True)),
                ('fecha_reclamada', models.DateTimeField(blank=True, null=True)),
                ('fecha_completada', models.DateTimeField(blank=True, null=True)),
                ('aliado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='misiones_empleabilidad', to='core.aliadoempleabilidad', verbose_name='Aliado')),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='misiones_empleabilidad', to='core.cliente', verbose_name='Cliente')),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='misiones_empleabilidad', to='core.estudiante', verbose_name='Estudiante')),
            ],
            options={
                'verbose_name': 'Misión de Empleabilidad',
                'verbose_name_plural': 'Misiones de Empleabilidad',
                'ordering': ['-fecha_descubierta'],
            },
        ),
        migrations.AddIndex(
            model_name='misionempleabilidad',
            index=models.Index(fields=['estudiante', 'estado', 'fecha_descubierta'], name='core_misione_estudia_2c88c4_idx'),
        ),
        migrations.AddIndex(
            model_name='misionempleabilidad',
            index=models.Index(fields=['cliente', 'estado', 'fecha_descubierta'], name='core_misione_cliente_7a9074_idx'),
        ),
        migrations.AddIndex(
            model_name='misionempleabilidad',
            index=models.Index(fields=['aliado', 'estado'], name='core_misione_aliado__ceb898_idx'),
        ),
    ]
