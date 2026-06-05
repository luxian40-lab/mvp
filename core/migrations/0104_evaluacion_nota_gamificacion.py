from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0103_cliente_modo_gamificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='peso_gamificacion_abierta',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('1'),
                help_text='Peso en el promedio ponderado del ranking (modo calificación).',
                max_digits=5,
                verbose_name='Peso de notas — pregunta abierta',
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='peso_gamificacion_reto',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('1'),
                help_text='Peso en el promedio ponderado del ranking (modo calificación).',
                max_digits=5,
                verbose_name='Peso de notas — reto',
            ),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='modo_gamificacion',
            field=models.CharField(
                choices=[
                    ('desactivado', 'Desactivada'),
                    ('puntos', 'Puntos (ranking y recompensas)'),
                    ('calificacion', 'Calificación 1–5 (ranking por promedio)'),
                ],
                default='puntos',
                help_text=(
                    'Puntos: ranking por puntos acumulados (actual). '
                    'Calificación 1–5: gamificación por notas (promedio ponderado para ranking; ej. 3,5). '
                    'Desactivada: sin gamificación visible.'
                ),
                max_length=20,
                verbose_name='Modo de gamificación',
            ),
        ),
        migrations.CreateModel(
            name='EvaluacionNotaGamificacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nota', models.DecimalField(
                    decimal_places=1,
                    help_text='Escala 1 a 5; admite decimales (ej. 3.5).',
                    max_digits=3,
                    verbose_name='Nota (1–5)',
                )),
                ('peso', models.DecimalField(
                    decimal_places=2,
                    default=1,
                    help_text='Peso para el promedio ponderado del ranking (ej. reto=2, abierta=1).',
                    max_digits=5,
                )),
                ('tipo', models.CharField(
                    choices=[
                        ('reto', 'Reto facilitadora'),
                        ('pregunta_abierta', 'Pregunta abierta final'),
                        ('manual', 'Manual (equipo)'),
                    ],
                    default='reto',
                    max_length=30,
                )),
                ('detalle', models.CharField(blank=True, default='', max_length=200)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('curso', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='evaluaciones_nota_gamificacion',
                    to='core.curso',
                )),
                ('estudiante', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='evaluaciones_nota_gamificacion',
                    to='core.estudiante',
                )),
                ('modulo', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='evaluaciones_nota_gamificacion',
                    to='core.modulo',
                )),
            ],
            options={
                'verbose_name': 'Evaluación por nota (gamificación)',
                'verbose_name_plural': 'Evaluaciones por nota (gamificación)',
                'ordering': ['-fecha'],
            },
        ),
        migrations.AddIndex(
            model_name='evaluacionnotagamificacion',
            index=models.Index(fields=['estudiante', '-fecha'], name='core_evalno_est_fecha_idx'),
        ),
    ]
