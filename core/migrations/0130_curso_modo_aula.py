from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0129_cliente_wallpaper_aula_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='curso',
            name='modo_aula',
            field=models.CharField(
                choices=[
                    ('modulos', 'Módulos (WhatsApp + avance)'),
                    ('clases', 'Clases / biblioteca (sin avance WA)'),
                ],
                default='modulos',
                help_text=(
                    'Clases: en Aprende se habla de «Clases», Biblioteca es el hub '
                    '(«mis clases guardadas») y no se menciona avance ni *listo*. '
                    'Ideal para curso C / 10x informativo.'
                ),
                max_length=20,
                verbose_name='Experiencia en aula',
            ),
        ),
    ]
