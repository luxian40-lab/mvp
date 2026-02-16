# Generated manually - Add cedula field (Step 1: nullable)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_plantilla_aprobada_twilio_and_more'),
    ]

    operations = [
        # Paso 1: Agregar campo nullable
        migrations.AddField(
            model_name='estudiante',
            name='cedula',
            field=models.CharField(
                max_length=20, 
                null=True, 
                blank=True,
                help_text='Número de identificación único (cédula de ciudadanía)', 
                verbose_name='Cédula'
            ),
        ),
    ]
