# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0095_alter_contextoagrosession_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MensajePush',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=120)),
                ('twilio_content_sid', models.CharField(blank=True, max_length=64)),
                ('tipo', models.CharField(
                    choices=[
                        ('recordatorio_inscripcion', 'Inscrito — aún no inicia'),
                        ('recordatorio_avance', 'Curso iniciado — sigue avanzando'),
                        ('recordatorio_modulo', 'Módulo disponible'),
                        ('personalizado', 'Personalizado'),
                    ],
                    default='recordatorio_avance',
                    max_length=32,
                )),
                ('cuerpo_fallback', models.TextField(blank=True, help_text='Texto libre si no hay SID. Variables: {nombre}, {curso}.')),
                ('incluir_boton_continuar', models.BooleanField(default=True)),
                ('activo', models.BooleanField(default=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='mensajes_push', to='core.cliente',
                )),
                ('curso', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='mensajes_push', to='core.curso',
                )),
                ('plantilla', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='mensajes_push', to='core.plantilla',
                )),
            ],
            options={
                'verbose_name': 'Mensaje push',
                'verbose_name_plural': 'Mensajes push',
                'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.CreateModel(
            name='EnvioMensajePush',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefono', models.CharField(max_length=20)),
                ('exito', models.BooleanField(default=False)),
                ('detalle', models.CharField(blank=True, max_length=255)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('estudiante', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='envios_push', to='core.estudiante',
                )),
                ('mensaje_push', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='envios', to='core.mensajepush',
                )),
            ],
            options={
                'verbose_name': 'Envío mensaje push',
                'verbose_name_plural': 'Envíos mensajes push',
                'ordering': ['-fecha'],
            },
        ),
    ]
