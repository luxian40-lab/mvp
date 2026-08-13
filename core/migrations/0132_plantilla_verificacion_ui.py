# Generated manually for PlantillaCertificado verificación pública UI

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0131_paso_media_wa_apto'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantillacertificado',
            name='verificacion_hero',
            field=models.CharField(
                choices=[
                    ('estudiante', 'Nombre del estudiante'),
                    ('curso', 'Nombre del curso'),
                    ('organizacion', 'Organización'),
                ],
                default='estudiante',
                help_text='Qué título va más grande en certificados.eki.technology al verificar.',
                max_length=20,
                verbose_name='Destacar en la ficha',
            ),
        ),
        migrations.AddField(
            model_name='plantillacertificado',
            name='verificacion_tamano_hero',
            field=models.CharField(
                choices=[('m', 'Normal'), ('l', 'Grande'), ('xl', 'Muy grande')],
                default='l',
                help_text='Tamaño tipográfico del elemento destacado.',
                max_length=4,
                verbose_name='Tamaño del título',
            ),
        ),
        migrations.AddField(
            model_name='plantillacertificado',
            name='verificacion_mostrar_diploma',
            field=models.BooleanField(
                default=True,
                help_text='Si hay imagen del certificado emitido, mostrarla en la ficha pública.',
                verbose_name='Mostrar miniatura del diploma',
            ),
        ),
        migrations.AddField(
            model_name='plantillacertificado',
            name='verificacion_mostrar_hash',
            field=models.BooleanField(
                default=True,
                help_text='Mostrar el hash de integridad en la ficha (más técnico).',
                verbose_name='Mostrar SHA-256',
            ),
        ),
    ]
