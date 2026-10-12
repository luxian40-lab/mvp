import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0181_conocimiento_alcance_agentes'),
    ]

    operations = [
        migrations.CreateModel(
            name='PruebaAgente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('agente', models.CharField(choices=[('coach', 'Coach eki'), ('ia_campo', 'Profesor IA'), ('ventas', 'Ventas eki'), ('finanzas', 'Experto en finanzas'), ('cafe', 'Experto en café')], max_length=16)),
                ('pregunta', models.TextField()),
                ('plan', models.CharField(blank=True, default='', max_length=20)),
                ('debe_mencionar', models.TextField(blank=True, default='')),
                ('no_debe_mencionar', models.TextField(blank=True, default='')),
                ('debe_usar_fuente', models.CharField(blank=True, default='', max_length=160)),
                ('ultima_corrida', models.DateTimeField(blank=True, null=True)),
                ('ultimo_resultado', models.CharField(blank=True, default='', max_length=16)),
                ('corridas', models.PositiveIntegerField(default=0)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pruebas_agente', to='core.cliente')),
            ],
            options={
                'verbose_name': 'Prueba de agente',
                'verbose_name_plural': 'Pruebas de agente',
                'ordering': ['-creado_en'],
            },
        ),
    ]
