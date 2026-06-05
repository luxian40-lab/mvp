from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0105_certificado_nota_minima_drip_estudiante'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='modo_avance_modulo',
            field=models.CharField(
                choices=[
                    ('texto', 'Solo escribir listo / continuar'),
                    ('boton', 'Solo botón WhatsApp (plantilla)'),
                    ('ambos', 'Texto y botón'),
                ],
                default='texto',
                help_text=(
                    'Cómo avanzan los estudiantes al terminar de ver un módulo. '
                    '«Texto» = comportamiento actual. «Botón» = plantilla Twilio al cierre del envío. '
                    'No aplica en onboarding, PQRS ni agentes IA.'
                ),
                max_length=20,
                verbose_name='Avance entre módulos',
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='content_sid_boton_listo',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Content SID (HX…) de plantilla con quick reply «Listo». '
                    'Vacío = usa la plantilla global continuar_modulo si el modo es botón.'
                ),
                max_length=64,
                verbose_name='Plantilla botón Listo (Twilio)',
            ),
        ),
    ]
