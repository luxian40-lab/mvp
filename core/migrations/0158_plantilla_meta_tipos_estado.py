from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0157_plan_por_grupo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plantillameta',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('TEXTO', 'Texto'),
                    ('IMAGEN', 'Imagen'),
                    ('VIDEO', 'Video'),
                    ('DOCUMENTO', 'Documento'),
                    ('UBICACION', 'Ubicación'),
                    ('CARRUSEL', 'Carrusel'),
                    ('OFERTA_LIMITADA', 'Oferta por tiempo limitado'),
                    ('CUPON', 'Cupón'),
                    ('CATALOGO', 'Catálogo'),
                    ('PRODUCTOS', 'Varios productos'),
                    ('FLUJO', 'Flujo'),
                    ('LLAMADA', 'Permiso de llamada'),
                    ('AUTENTICACION', 'Autenticación (código)'),
                    ('PEDIDO', 'Pedido (estado o detalle)'),
                ],
                default='TEXTO',
                help_text='Formato en Meta. El alta automática cubre Texto y Carrusel; los demás quedan guardados como registro.',
                max_length=16,
                verbose_name='Tipo',
            ),
        ),
        migrations.AlterField(
            model_name='plantillameta',
            name='estado',
            field=models.CharField(
                choices=[
                    ('BORRADOR', 'Borrador'),
                    ('PENDING', 'Pendiente'),
                    ('APPROVED', 'Aprobada'),
                    ('REJECTED', 'Rechazada'),
                    ('PAUSED', 'Pausada'),
                    ('DISABLED', 'Deshabilitada'),
                    ('IN_APPEAL', 'En apelación'),
                    ('ERROR', 'Error'),
                ],
                db_index=True,
                default='BORRADOR',
                help_text='Márquelo al guardar. Use Aprobada solo si Meta ya la aceptó. Sincronizar o el webhook pueden actualizar este valor. Las campañas solo se envían si está Aprobada.',
                max_length=20,
                verbose_name='Estado',
            ),
        ),
    ]
