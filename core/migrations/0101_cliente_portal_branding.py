from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0100_cliente_fecha_fin_suscripcion_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='logo_url',
            field=models.URLField(
                blank=True,
                help_text='URL pública del logo de la organización. Visible en el portal B2B.',
                max_length=500,
                verbose_name='Logo (portal)',
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='portal_subtitulo',
            field=models.CharField(
                blank=True,
                help_text='Texto corto bajo el nombre en el portal (ej: Cooperativa del Valle — 2026).',
                max_length=200,
                verbose_name='Subtítulo en portal',
            ),
        ),
    ]
