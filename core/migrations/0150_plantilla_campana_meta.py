import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0148_sandbox_habeas_menu'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlantillaMeta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_interno', models.CharField(max_length=120, verbose_name='Nombre interno')),
                ('meta_name', models.CharField(blank=True, help_text='Minúsculas y guion bajo. Si se deja vacío, se arma desde el nombre interno.', max_length=512, verbose_name='Nombre en Meta')),
                ('idioma', models.CharField(default='es', max_length=10, verbose_name='Idioma')),
                ('categoria', models.CharField(choices=[('MARKETING', 'Marketing'), ('UTILITY', 'Utilidad'), ('AUTHENTICATION', 'Autenticación')], default='UTILITY', max_length=20, verbose_name='Categoría Meta')),
                ('header_texto', models.CharField(blank=True, help_text='Opcional. Texto, puede incluir {{1}}.', max_length=60, verbose_name='Header')),
                ('header_ejemplo', models.CharField(blank=True, help_text='Obligatorio si el header tiene {{1}}.', max_length=60, verbose_name='Ejemplo del header')),
                ('cuerpo', models.TextField(help_text='Texto que ve la persona. Variables {{1}}, {{2}}…', verbose_name='Cuerpo')),
                ('ejemplos_cuerpo', models.CharField(blank=True, help_text='Un valor por variable, separados por |. Ej: Ana|Café', max_length=500, verbose_name='Ejemplos del cuerpo')),
                ('footer', models.CharField(blank=True, max_length=60, verbose_name='Footer')),
                ('boton_1_tipo', models.CharField(blank=True, choices=[('', 'Sin botón'), ('QUICK_REPLY', 'Respuesta rápida'), ('URL', 'Enlace')], default='', max_length=20, verbose_name='Botón 1')),
                ('boton_1_texto', models.CharField(blank=True, max_length=25, verbose_name='Texto botón 1')),
                ('boton_1_url', models.CharField(blank=True, help_text='Si lleva variable, termina en {{1}}. Ej: https://app.eki.technology/c/{{1}}', max_length=2000, verbose_name='URL botón 1')),
                ('boton_1_ejemplo', models.CharField(blank=True, max_length=200, verbose_name='Ejemplo URL botón 1')),
                ('boton_2_tipo', models.CharField(blank=True, choices=[('', 'Sin botón'), ('QUICK_REPLY', 'Respuesta rápida'), ('URL', 'Enlace')], default='', max_length=20, verbose_name='Botón 2')),
                ('boton_2_texto', models.CharField(blank=True, max_length=25, verbose_name='Texto botón 2')),
                ('boton_2_url', models.CharField(blank=True, max_length=2000, verbose_name='URL botón 2')),
                ('boton_2_ejemplo', models.CharField(blank=True, max_length=200, verbose_name='Ejemplo URL botón 2')),
                ('meta_template_id', models.CharField(blank=True, default='', max_length=64, verbose_name='ID en Meta')),
                ('waba_id', models.CharField(blank=True, default='', max_length=64, verbose_name='WABA')),
                ('estado', models.CharField(choices=[('BORRADOR', 'Borrador'), ('PENDING', 'Pendiente'), ('APPROVED', 'Aprobada'), ('REJECTED', 'Rechazada'), ('PAUSED', 'Pausada'), ('DISABLED', 'Deshabilitada'), ('IN_APPEAL', 'En apelación'), ('ERROR', 'Error')], db_index=True, default='BORRADOR', max_length=20, verbose_name='Estado')),
                ('rejected_reason', models.CharField(blank=True, default='', max_length=500, verbose_name='Motivo')),
                ('ultimo_error_code', models.CharField(blank=True, default='', max_length=32, verbose_name='Código error')),
                ('ultimo_error_mensaje', models.TextField(blank=True, default='', verbose_name='Error Meta')),
                ('activa', models.BooleanField(default=True, verbose_name='Activa')),
                ('enviada_en', models.DateTimeField(blank=True, null=True, verbose_name='Enviada a Meta')),
                ('sincronizada_en', models.DateTimeField(blank=True, null=True, verbose_name='Última sync')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Plantilla Meta',
                'verbose_name_plural': 'Plantillas Meta',
                'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.CreateModel(
            name='CampanaMeta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=120)),
                ('mapeo_header', models.CharField(blank=True, default='', help_text='Si el header tiene {{1}}: nombre, telefono, o un texto fijo. Varias, separadas por |.', max_length=200, verbose_name='Variables del header')),
                ('mapeo_body', models.CharField(blank=True, default='nombre', help_text='Una por cada {{n}}, separadas por |. nombre y telefono salen del estudiante; el resto es texto fijo.', max_length=300, verbose_name='Variables del cuerpo')),
                ('mapeo_boton', models.CharField(blank=True, default='', help_text='Si algún botón URL lleva {{1}}. Misma regla: nombre, telefono o texto fijo.', max_length=200, verbose_name='Variable del botón URL')),
                ('phone_number_id', models.CharField(blank=True, default='', help_text='Vacío usa WHATSAPP_PHONE_ID (línea Cloud API). No es el número de Twilio.', max_length=32, verbose_name='Phone number ID')),
                ('ejecutada', models.BooleanField(default=False, verbose_name='Ejecutada')),
                ('total_enviados', models.IntegerField(default=0, verbose_name='Enviados')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campanas_meta', to='core.cliente', verbose_name='Cliente')),
                ('grupo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campanas_meta', to='core.grupoestudiantes', verbose_name='Grupo')),
                ('plantilla', models.ForeignKey(help_text='Tiene que estar Aprobada para poder enviarla.', on_delete=django.db.models.deletion.PROTECT, related_name='campanas', to='core.plantillameta', verbose_name='Plantilla Meta')),
            ],
            options={
                'verbose_name': 'Campaña Meta',
                'verbose_name_plural': 'Campañas Meta',
                'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.CreateModel(
            name='EnvioCampanaMeta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[('ENVIADO', 'Enviado'), ('FALLIDO', 'Fallido')], default='FALLIDO', max_length=20)),
                ('wamid', models.CharField(blank=True, default='', max_length=200)),
                ('respuesta', models.TextField(blank=True, default='')),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('campana', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='envios', to='core.campanameta')),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='envios_campana_meta', to='core.estudiante')),
            ],
            options={
                'verbose_name': 'Envío campaña Meta',
                'verbose_name_plural': 'Envíos campaña Meta',
                'ordering': ['-fecha'],
            },
        ),
        migrations.AddField(
            model_name='campanameta',
            name='destinatarios',
            field=models.ManyToManyField(blank=True, related_name='campanas_meta', to='core.estudiante', verbose_name='Destinatarios'),
        ),
        migrations.AddConstraint(
            model_name='plantillameta',
            constraint=models.UniqueConstraint(fields=('meta_name', 'idioma'), name='uniq_plantilla_meta_nombre_idioma'),
        ),
    ]
