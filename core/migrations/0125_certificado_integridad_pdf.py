from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0124_producto_nat_imagen_stock'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificado',
            name='hash_sha256',
            field=models.CharField(
                blank=True,
                default='',
                help_text='SHA-256 del PNG del diploma (integridad del artefacto)',
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name='certificado',
            name='organizacion_emisora',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Snapshot del nombre de la organización al emitir',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='certificado',
            name='anulado',
            field=models.BooleanField(
                default=False,
                help_text='Si está anulado, la verificación pública lo marca no válido',
            ),
        ),
        migrations.AddField(
            model_name='certificado',
            name='fecha_anulacion',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='certificado',
            name='motivo_anulacion',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
