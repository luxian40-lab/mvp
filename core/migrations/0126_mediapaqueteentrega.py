from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0125_certificado_integridad_pdf'),
    ]

    operations = [
        migrations.CreateModel(
            name='MediaPaqueteEntrega',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefono', models.CharField(db_index=True, max_length=30)),
                ('media_url', models.TextField(blank=True, default='')),
                ('estado', models.CharField(
                    choices=[
                        ('pendiente', 'Pendiente'),
                        ('enviado', 'Enviado'),
                        ('fallido', 'Fallido'),
                        ('recuperado', 'Recuperado'),
                    ],
                    db_index=True,
                    default='enviado',
                    max_length=20,
                )),
                ('intentos', models.PositiveSmallIntegerField(default=0)),
                ('error_code', models.CharField(blank=True, default='', max_length=20)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('curso', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='paquetes_media', to='core.curso',
                )),
                ('estudiante', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='paquetes_media', to='core.estudiante',
                )),
                ('modulo', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='paquetes_media', to='core.modulo',
                )),
                ('whatsapp_log', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='paquetes_media', to='core.whatsapplog',
                )),
            ],
            options={
                'verbose_name': 'Paquete media WhatsApp',
                'verbose_name_plural': 'Paquetes media WhatsApp',
                'ordering': ['-actualizado_en'],
            },
        ),
        migrations.AddIndex(
            model_name='mediapaqueteentrega',
            index=models.Index(fields=['telefono', 'estado'], name='core_mediap_telefon_8a1c2d_idx'),
        ),
        migrations.AddIndex(
            model_name='mediapaqueteentrega',
            index=models.Index(fields=['estado', '-actualizado_en'], name='core_mediap_estado_9b2e3f_idx'),
        ),
    ]
