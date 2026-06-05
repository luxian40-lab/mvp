# Generated manually — línea WhatsApp Nat por organización

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0098_producto_catalogo_nat'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='numero_whatsapp_nat',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Número Twilio al que escribe el productor para hablar con Nat (solo dígitos, ej: 573001234567). '
                    'Cada organización puede tener su propia línea; el webhook identifica el cliente por este número (campo To). '
                    'Distinto del número de campañas educativas y del BOT_COMERCIAL_CLIENTE_ID global.'
                ),
                max_length=20,
                verbose_name='Número WhatsApp Nat (línea comercial)',
            ),
        ),
    ]
