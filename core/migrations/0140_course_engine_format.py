# Generated manually — Course Engine formato curso

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0139_course_engine_voice_tier'),
    ]

    operations = [
        migrations.AddField(
            model_name='curso',
            name='course_engine_format',
            field=models.CharField(
                choices=[
                    ('solo_video', 'Solo video MP4 (1 paso WA)'),
                    ('video_infografia', 'Video + infografía PNG (2 pasos)'),
                    ('mixto_completo', 'Mixto completo: video + infografía + podcast (3 pasos)'),
                    ('mixto_ligero', 'Ligero: video económico sin podcast ni PNG suelta'),
                ],
                default='video_infografia',
                help_text='Como se segmenta cada modulo al generar contenido IA (pasos WhatsApp).',
                max_length=24,
                verbose_name='Formato Course Engine (segmentacion)',
            ),
        ),
        migrations.AddField(
            model_name='curso',
            name='course_engine_podcast_minutos',
            field=models.PositiveSmallIntegerField(
                choices=[(2, '2 min'), (3, '3 min'), (4, '4 min')],
                default=2,
                help_text='Duracion objetivo del podcast en formato mixto_completo.',
                verbose_name='Podcast (minutos)',
            ),
        ),
    ]
