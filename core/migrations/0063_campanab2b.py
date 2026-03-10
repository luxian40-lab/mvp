# Generated manually - Django 5.2.9

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0062_add_preguntas_ejemplo_ia'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampanaB2B',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(help_text='Ej: Propuesta Café Huila 2026', max_length=200, verbose_name='Nombre de la Campaña')),
                ('mensaje', models.TextField(blank=True, default='', help_text='Texto del mensaje a enviar. Usa {nombre} para personalizar con el nombre del prospecto.', verbose_name='Mensaje de texto')),
                ('twilio_template_sid', models.CharField(blank=True, help_text='Si se especifica, se envía este template en lugar del mensaje de texto.', max_length=50, verbose_name='Content SID de Twilio (opcional)')),
                ('url_media', models.URLField(blank=True, help_text='URL pública del PDF o archivo a adjuntar.', max_length=500, verbose_name='URL del PDF/Media (opcional)')),
                ('estado', models.CharField(choices=[('borrador', 'Borrador'), ('enviada', 'Enviada')], default='borrador', max_length=20)),
                ('total_enviados', models.IntegerField(default=0)),
                ('total_errores', models.IntegerField(default=0)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_envio', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Campaña B2B',
                'verbose_name_plural': '📤 Campañas B2B',
                'ordering': ['-fecha_creacion'],
            },
        ),
    ]
