import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0074_remove_agro_nexo_canal_comercial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionDripCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'dias_espera_entre_modulos',
                    models.IntegerField(
                        blank=True,
                        help_text='Vacío = usar el valor configurado en el curso. 0 = sin espera para este cliente. N = N días entre módulos.',
                        null=True,
                        verbose_name='Días de espera (override)',
                    ),
                ),
                (
                    'activo',
                    models.BooleanField(
                        default=True,
                        help_text='Si está desactivado, se ignora esta fila y se usa solo el curso.',
                        verbose_name='Activo',
                    ),
                ),
                (
                    'cliente',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='configuraciones_drip_curso',
                        to='core.cliente',
                        verbose_name='Cliente',
                    ),
                ),
                (
                    'curso',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='configuraciones_drip_cliente',
                        to='core.curso',
                        verbose_name='Curso',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Configuración drip (cliente × curso)',
                'verbose_name_plural': 'Configuraciones drip (cliente × curso)',
            },
        ),
        migrations.AddConstraint(
            model_name='configuraciondripcliente',
            constraint=models.UniqueConstraint(fields=('cliente', 'curso'), name='uniq_drip_cliente_curso'),
        ),
    ]
