from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0205_certificado_imagen_whatsapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantillacertificado',
            name='layout_stickers',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    'Click en la vista previa (nombre, cédula, fecha, QR). '
                    'Vacío = marcadores RGB de Canva.'
                ),
                verbose_name='Posiciones en el diploma',
            ),
        ),
    ]
