from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0123_seed_certificado_demo_verificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='productocatalogo',
            name='sku',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Opcional. Si coincide con un SKU de Precios, Nat une ficha + precio + stock.',
                max_length=80,
                verbose_name='SKU / código',
            ),
        ),
        migrations.AddField(
            model_name='productocatalogo',
            name='imagen',
            field=models.ImageField(
                blank=True,
                help_text='Imagen del empaque o presentación (JPG/PNG/WebP). Se guarda en S3 en producción.',
                null=True,
                upload_to='nat/productos/%Y/%m/',
                verbose_name='Foto del producto',
            ),
        ),
        migrations.AddField(
            model_name='productocomercial',
            name='stock',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Unidades en bodega (opcional). Vacío = no se reporta inventario.',
                null=True,
                verbose_name='Stock disponible',
            ),
        ),
    ]
