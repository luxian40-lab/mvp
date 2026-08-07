# Generated manually for Module Builder WA — solo media_wa_apto

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0130_curso_modo_aula'),
    ]

    operations = [
        migrations.AddField(
            model_name='pasomodulo',
            name='media_wa_apto',
            field=models.BooleanField(
                blank=True,
                default=None,
                help_text=(
                    'True si el último upload de video pasó compresión/gate WA (~16MB, H.264). '
                    'Vacío = legado / desconocido. No reprocesa videos antiguos solos.'
                ),
                null=True,
                verbose_name='Apto WhatsApp',
            ),
        ),
    ]
