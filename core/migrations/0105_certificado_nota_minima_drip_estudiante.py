from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0104_evaluacion_nota_gamificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='drip_modulos_solo_estudiantes_listados',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Si está activo, cada módulo solo es accesible para estudiantes con '
                    '«Habilitación de módulo (estudiante)» en el admin. El drip general del cliente sigue '
                    'aplicando fechas; la lista define quién puede entrar.'
                ),
                verbose_name='Módulos solo por lista de estudiantes',
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='exigir_nota_minima_certificado',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Opcional. Solo aplica en modo «Calificación 1–5». Si el promedio ponderado '
                    'es menor a la nota mínima, no se emite certificado.'
                ),
                verbose_name='Exigir nota mínima para certificado',
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='nota_minima_certificado',
            field=models.DecimalField(
                decimal_places=1,
                default=Decimal('3'),
                help_text='Umbral de aprobación (ej. 3 o 3.5). Por debajo: curso completado sin certificado.',
                max_digits=3,
                verbose_name='Nota mínima certificado (1–5)',
            ),
        ),
        migrations.CreateModel(
            name='HabilitacionModuloEstudiante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('habilitado_desde', models.DateTimeField(
                    blank=True,
                    help_text=(
                        'Opcional. Si se define, sustituye la fecha del cliente para este estudiante. '
                        'Vacío = sin fecha extra (solo inclusión en la lista).'
                    ),
                    null=True,
                    verbose_name='Disponible desde (este estudiante)',
                )),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('notas', models.CharField(blank=True, default='', max_length=200, verbose_name='Notas internas')),
                ('curso', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='habilitaciones_modulo_estudiante',
                    to='core.curso',
                    verbose_name='Curso',
                )),
                ('estudiante', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='habilitaciones_modulo_individual',
                    to='core.estudiante',
                    verbose_name='Estudiante',
                )),
                ('modulo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='habilitaciones_estudiante',
                    to='core.modulo',
                    verbose_name='Módulo',
                )),
            ],
            options={
                'verbose_name': 'Habilitación de módulo (estudiante)',
                'verbose_name_plural': 'Habilitaciones de módulos por estudiante',
            },
        ),
        migrations.AddConstraint(
            model_name='habilitacionmoduloestudiante',
            constraint=models.UniqueConstraint(
                fields=('estudiante', 'curso', 'modulo'),
                name='uniq_habilitacion_modulo_estudiante',
            ),
        ),
    ]
