# Generated manually for LatAm document types

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0126_mediapaqueteentrega'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estudiante',
            name='tipo_documento',
            field=models.CharField(
                choices=[
                    ('CC', 'Cédula de Ciudadanía (CO)'),
                    ('TI', 'Tarjeta de Identidad (CO)'),
                    ('CE', 'Cédula de Extranjería (CO)'),
                    ('DUI', 'DUI — Documento Único de Identidad (SV)'),
                    ('CURP', 'CURP (MX)'),
                    ('INE', 'Credencial INE / IFE (MX)'),
                    ('DNI', 'DNI — Documento Nacional de Identidad'),
                    ('RUT', 'RUT (CL)'),
                    ('DPI', 'DPI (GT)'),
                    ('CI', 'Cédula de Identidad (LatAm)'),
                    ('PP', 'Pasaporte'),
                    ('OTRO', 'Otro documento / ID'),
                ],
                default='CC',
                help_text='Tipo de documento (CC Colombia, DUI El Salvador, CURP/INE México, DNI, RUT, etc.)',
                max_length=8,
                verbose_name='Tipo de Documento',
            ),
        ),
        migrations.AlterField(
            model_name='estudiante',
            name='cedula',
            field=models.CharField(
                help_text='Número/ID único (cédula, DUI, CURP, DNI…). Sin puntos ni espacios; puede incluir letras.',
                max_length=32,
                unique=True,
                verbose_name='Número de Documento',
            ),
        ),
    ]
