from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0075_configuracion_drip_cliente'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='enlace_habeas_data',
            field=models.URLField(
                blank=True,
                help_text='Opcional: URL de política de datos propia del cliente. Si se deja vacío, se usa la URL general de eki.',
                max_length=700,
                verbose_name='Enlace Habeas Data (override)',
            ),
        ),
    ]
