# Generated migration for Etiqueta model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_plantilla_proveedor_plantilla_twilio_template_sid'),
    ]

    operations = [
        migrations.CreateModel(
            name='Etiqueta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True, verbose_name='Nombre')),
                ('color', models.CharField(default='#667eea', max_length=7, verbose_name='Color')),
                ('descripcion', models.TextField(blank=True, verbose_name='Descripción')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
            ],
            options={
                'verbose_name': 'Etiqueta',
                'verbose_name_plural': 'Etiquetas',
                'ordering': ['nombre'],
            },
        ),
        migrations.AddField(
            model_name='estudiante',
            name='etiquetas',
            field=models.ManyToManyField(blank=True, related_name='estudiantes', to='core.etiqueta', verbose_name='Etiquetas'),
        ),
    ]
