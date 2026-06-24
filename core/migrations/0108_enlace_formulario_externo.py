# Generated for Google Form → habilitar módulo

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0107_plantillacertificado_modo_plantilla'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnlaceFormularioExterno',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(help_text='Ej: Google Form pre-evaluación M5', max_length=120)),
                ('campo_identificador', models.CharField(
                    choices=[('cedula', 'Cédula / documento'), ('telefono', 'Teléfono WhatsApp')],
                    default='cedula',
                    max_length=16,
                    verbose_name='Campo del formulario para identificar',
                )),
                ('token', models.CharField(editable=False, max_length=64, unique=True)),
                ('activo', models.BooleanField(default=True)),
                ('notas', models.TextField(blank=True, default='')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enlaces_formulario_externo',
                    to='core.cliente',
                )),
                ('curso', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enlaces_formulario_externo',
                    to='core.curso',
                )),
                ('modulo', models.ForeignKey(
                    blank=True,
                    help_text='Vacío = último módulo del curso (mayor número).',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enlaces_formulario_externo',
                    to='core.modulo',
                )),
            ],
            options={
                'verbose_name': 'Enlace formulario externo',
                'verbose_name_plural': 'Enlaces formulario externo (Google Form)',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.CreateModel(
            name='RegistroFormularioExterno',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identificador_recibido', models.CharField(blank=True, default='', max_length=80)),
                ('exito', models.BooleanField(default=False)),
                ('detalle', models.CharField(blank=True, default='', max_length=255)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('enlace', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='registros',
                    to='core.enlaceformularioexterno',
                )),
                ('estudiante', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='registros_form_externo',
                    to='core.estudiante',
                )),
            ],
            options={
                'verbose_name': 'Registro formulario externo',
                'verbose_name_plural': 'Registros formulario externo',
                'ordering': ['-fecha'],
            },
        ),
    ]
