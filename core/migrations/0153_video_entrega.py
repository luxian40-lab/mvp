from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0149_video_enlace_vista'),
        ('core', '0152_plantilla_carrusel_tarjeta'),
    ]

    operations = [
        migrations.AddField(
            model_name='pasomodulo',
            name='video_entrega',
            field=models.CharField(
                choices=[
                    ('whatsapp', 'WhatsApp directo'),
                    ('enlace', 'videos.eki.technology'),
                ],
                default='whatsapp',
                help_text=(
                    'Solo aplica si el archivo es video. WhatsApp directo lo adjunta. '
                    'El enlace abre el reproductor de eki y cuenta la apertura.'
                ),
                max_length=16,
                verbose_name='Entrega del video',
            ),
        ),
    ]
