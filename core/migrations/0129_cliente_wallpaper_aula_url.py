# Generated manually for wallpaper_aula_url

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0128_estudiante_territory_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='wallpaper_aula_url',
            field=models.URLField(
                blank=True,
                help_text=(
                    'Fondo de la sesión estudiante en Aprende. JPG/WebP recomendado ≤ 2 MB, '
                    'ancho ≥ 1600px. Vacío = fondo eki por defecto.'
                ),
                max_length=500,
                verbose_name='Wallpaper aula (Aprende)',
            ),
        ),
    ]
