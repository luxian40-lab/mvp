# Generated manually for MargenUsoEvento telemetry

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('calculadora_margen', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MargenUsoEvento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('curso_id', models.PositiveIntegerField(blank=True, null=True)),
                ('session_key', models.CharField(db_index=True, max_length=64)),
                ('evento', models.CharField(
                    choices=[
                        ('apertura', 'Apertura'),
                        ('inicio_wizard', 'Inicio wizard'),
                        ('calculo_ok', 'Cálculo completado'),
                        ('resultado_visto', 'Resultado visto'),
                        ('simulo_precio', 'Simuló precio'),
                        ('recomendaciones_ok', 'Recomendaciones IA'),
                    ],
                    db_index=True,
                    max_length=32,
                )),
                ('margen_rango', models.CharField(blank=True, default='', max_length=20)),
                ('meta', models.JSONField(blank=True, default=dict)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='margen_eventos',
                    to='core.cliente',
                )),
            ],
            options={
                'verbose_name': 'Evento calculadora margen',
                'verbose_name_plural': 'Eventos calculadora margen',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.AddIndex(
            model_name='margenusoevento',
            index=models.Index(fields=['cliente', 'evento', 'creado_en'], name='calc_margen_cli_evt_idx'),
        ),
    ]
