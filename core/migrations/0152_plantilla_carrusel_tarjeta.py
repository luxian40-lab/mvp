from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0151_catalogo_menu'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantillameta',
            name='tipo',
            field=models.CharField(
                choices=[('TEXTO', 'Texto'), ('CARRUSEL', 'Carrusel')],
                default='TEXTO',
                help_text='El carrusel se crea en Meta con la acción «Enviar plantilla a Meta para aprobación».',
                max_length=16,
                verbose_name='Tipo',
            ),
        ),
        migrations.CreateModel(
            name='TarjetaPlantillaMeta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('orden', models.PositiveIntegerField(default=0)),
                ('titulo', models.CharField(max_length=200)),
                ('cuerpo', models.CharField(max_length=160)),
                ('imagen_url', models.URLField(max_length=1000)),
                ('boton_ver_id', models.CharField(max_length=64)),
                ('boton_ver_texto', models.CharField(default='Ver curso', max_length=20)),
                ('boton_info_id', models.CharField(max_length=64)),
                ('boton_info_texto', models.CharField(default='Más información', max_length=20)),
                ('info_url', models.URLField(blank=True, default='', max_length=2000)),
                ('plantilla', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tarjetas', to='core.plantillameta')),
            ],
            options={
                'verbose_name': 'Tarjeta de carrusel',
                'verbose_name_plural': 'Tarjetas de carrusel',
                'ordering': ['plantilla', 'orden', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='tarjetaplantillameta',
            constraint=models.UniqueConstraint(fields=('plantilla', 'orden'), name='uniq_tarjeta_plantilla_orden'),
        ),
    ]
