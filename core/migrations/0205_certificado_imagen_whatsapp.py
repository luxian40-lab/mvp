from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0204_outbox_envio'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificado',
            name='archivo_imagen_whatsapp',
            field=models.ImageField(
                blank=True,
                help_text='Copia liviana del diploma para WhatsApp. Vacío = se envía archivo_imagen.',
                null=True,
                upload_to='Certificadosestudiantes/',
            ),
        ),
    ]
