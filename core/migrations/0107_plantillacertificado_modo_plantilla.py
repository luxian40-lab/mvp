from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0106_cliente_modo_avance_modulo'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantillacertificado',
            name='modo_plantilla',
            field=models.CharField(
                choices=[
                    ('imagen', 'Imagen (S3 / archivo con marcadores)'),
                    ('diseno_eki', 'Diseño eki (colores y textos)'),
                    ('pdf', 'PDF personalizado'),
                ],
                default='imagen',
                help_text='Define cómo se generará el certificado para esta plantilla.',
                max_length=20,
                verbose_name='Modo de plantilla',
            ),
        ),
    ]
