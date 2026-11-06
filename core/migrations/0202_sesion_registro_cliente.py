from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0201_plantilla_certificado_fuentes'),
    ]

    operations = [
        migrations.AddField(
            model_name='sandboxcanalsesion',
            name='registro_cliente_id',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Cliente que trajo el enlace de la línea 3. Vacío en las otras líneas.',
                null=True,
                verbose_name='Organización del enlace',
            ),
        ),
    ]
