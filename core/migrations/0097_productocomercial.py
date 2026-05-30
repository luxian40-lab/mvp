# Generated migration for ProductoComercial

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0096_mensajepush'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductoComercial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sku', models.CharField(help_text='Identificador único por cliente (ej: UREA-46-50KG).', max_length=80, verbose_name='SKU / código')),
                ('nombre', models.CharField(max_length=200, verbose_name='Nombre del producto')),
                ('presentacion', models.CharField(blank=True, default='', help_text='Ej: bulto 50 kg, garrafa 1 L.', max_length=120, verbose_name='Presentación')),
                ('unidad', models.CharField(blank=True, default='', help_text='Ej: bulto, kg, litro.', max_length=40, verbose_name='Unidad de venta')),
                ('precio', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Precio')),
                ('moneda', models.CharField(default='COP', max_length=8, verbose_name='Moneda')),
                ('categoria', models.CharField(blank=True, default='', help_text='Ej: fertilizante, herbicida, fungicida.', max_length=80, verbose_name='Categoría')),
                ('notas', models.TextField(blank=True, default='', verbose_name='Notas comerciales')),
                ('vigencia_desde', models.DateField(blank=True, null=True, verbose_name='Vigente desde')),
                ('vigencia_hasta', models.DateField(blank=True, null=True, verbose_name='Vigente hasta')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(blank=True, help_text='Vacío = catálogo general visible para todos los clientes.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='productos_comerciales', to='core.cliente', verbose_name='Cliente')),
            ],
            options={
                'verbose_name': 'Producto comercial (precio)',
                'verbose_name_plural': 'Productos comerciales (precios)',
                'ordering': ['nombre', 'sku'],
            },
        ),
        migrations.AddIndex(
            model_name='productocomercial',
            index=models.Index(fields=['cliente', 'activo', '-fecha_actualizacion'], name='core_produc_cliente_8a1f2d_idx'),
        ),
        migrations.AddIndex(
            model_name='productocomercial',
            index=models.Index(fields=['nombre'], name='core_produc_nombre_4c9b1e_idx'),
        ),
        migrations.AddIndex(
            model_name='productocomercial',
            index=models.Index(fields=['categoria'], name='core_produc_categor_2f7a9c_idx'),
        ),
        migrations.AddConstraint(
            model_name='productocomercial',
            constraint=models.UniqueConstraint(fields=('cliente', 'sku'), name='uniq_producto_comercial_cliente_sku'),
        ),
    ]
