from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0162_whatsapplog_error_codigo'),
    ]

    operations = [
        migrations.CreateModel(
            name='UsoLLM',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefono_hash', models.CharField(blank=True, default='', max_length=64)),
                ('agente', models.CharField(blank=True, default='', max_length=64)),
                ('modelo', models.CharField(max_length=64)),
                ('tokens_in', models.PositiveIntegerField(default=0)),
                ('tokens_out', models.PositiveIntegerField(default=0)),
                ('tokens_razonamiento', models.PositiveIntegerField(blank=True, null=True)),
                ('costo_usd_est', models.DecimalField(decimal_places=6, default=Decimal('0'), max_digits=10)),
                ('estimado', models.BooleanField(default=False)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='usos_llm',
                    to='core.cliente',
                )),
            ],
            options={
                'indexes': [
                    models.Index(fields=['cliente', 'creado'], name='uso_llm_cliente_creado'),
                ],
            },
        ),
    ]
