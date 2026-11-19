from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0210_certificado_calificacion_final_nullable'),
    ]

    operations = [
        migrations.CreateModel(
            name='BoletinEki',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=200)),
                ('cuerpo', models.TextField(help_text='HTML simple (párrafos, listas). Se muestra en /admin/novedades-eki/.')),
                ('periodo_inicio', models.DateField(blank=True, null=True)),
                ('periodo_fin', models.DateField(blank=True, null=True)),
                ('publicado', models.BooleanField(default=False, help_text='Solo uno puede estar publicado. Al marcar este, se despublican los demás.')),
                ('actualizado', models.DateTimeField(auto_now=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Boletín eki',
                'verbose_name_plural': 'Boletines eki',
                'ordering': ['-actualizado'],
            },
        ),
    ]
