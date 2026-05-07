# Generated manually for SeccionModulo + secciones_por_listo + PasoModulo.seccion

import django.db.models.deletion
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def crear_secciones_y_vincular_pasos(apps, schema_editor):
    PasoModulo = apps.get_model('core', 'PasoModulo')
    SeccionModulo = apps.get_model('core', 'SeccionModulo')
    for paso in PasoModulo.objects.all().order_by('modulo_id', 'orden', 'id'):
        sec = SeccionModulo.objects.create(
            modulo_id=paso.modulo_id,
            orden=paso.orden,
            titulo='',
            activa=True,
        )
        paso.seccion_id = sec.id
        paso.save(update_fields=['seccion_id'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0085_modulo_modo_entrega'),
    ]

    operations = [
        migrations.CreateModel(
            name='SeccionModulo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('orden', models.PositiveIntegerField(help_text='Orden de la sección dentro del módulo (1, 2, 3…).')),
                (
                    'titulo',
                    models.CharField(
                        blank=True,
                        help_text='Encabezado opcional al comenzar esta sección en WhatsApp.',
                        max_length=200,
                    ),
                ),
                ('activa', models.BooleanField(default=True)),
                (
                    'modulo',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='secciones',
                        to='core.modulo',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Sección',
                'verbose_name_plural': 'Secciones',
                'ordering': ['modulo', 'orden', 'id'],
            },
        ),
        migrations.AddField(
            model_name='modulo',
            name='secciones_por_listo',
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text='Cantidad de secciones (bloques con título propio) que se envían cada vez que el estudiante escribe *listo*. Dentro de cada sección pueden haber varios pasos. Valor entre 1 y 5.',
                validators=[MinValueValidator(1), MaxValueValidator(5)],
                verbose_name='Secciones por *listo*',
            ),
        ),
        migrations.AddField(
            model_name='pasomodulo',
            name='seccion',
            field=models.ForeignKey(
                help_text='Sección (bloque) a la que pertenece este paso.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='pasos',
                to='core.seccionmodulo',
            ),
        ),
        migrations.AddConstraint(
            model_name='seccionmodulo',
            constraint=models.UniqueConstraint(fields=('modulo', 'orden'), name='uniq_seccionmodulo_modulo_orden'),
        ),
        migrations.RunPython(crear_secciones_y_vincular_pasos, noop_reverse),
        migrations.AlterField(
            model_name='pasomodulo',
            name='seccion',
            field=models.ForeignKey(
                help_text='Sección (bloque) a la que pertenece este paso.',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='pasos',
                to='core.seccionmodulo',
            ),
        ),
    ]
