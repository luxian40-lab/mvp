# Enlaces únicos por cliente para calculadora margen

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('calculadora_margen', '0002_margenusoevento'),
    ]

    operations = [
        migrations.CreateModel(
            name='MargenEnlaceCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(help_text='Segmento legible para ?org= (ej. cooperativa-valle)', max_length=50, unique=True)),
                ('token', models.CharField(db_index=True, help_text='Token opaco para ?t= (compartir sin revelar nombre)', max_length=32, unique=True)),
                ('activo', models.BooleanField(default=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('cliente', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='margen_enlace', to='core.cliente')),
            ],
            options={
                'verbose_name': 'Enlace calculadora margen',
                'verbose_name_plural': 'Enlaces calculadora margen',
            },
        ),
    ]
