# Generated manually for Parte 2A — EventoIA

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0091_metas_metricas_empresa_nati'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventoIA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trace_id', models.UUIDField(db_index=True, verbose_name='Trace ID')),
                ('tipo', models.CharField(
                    choices=[
                        ('modulo_completado', 'Módulo completado'),
                        ('checkpoint_evaluado', 'Checkpoint evaluado'),
                        ('ia_agent_triggered', 'Agente IA activado'),
                        ('rag_query_executed', 'Consulta RAG'),
                    ],
                    db_index=True,
                    max_length=40,
                )),
                ('agente', models.CharField(blank=True, default='', max_length=60)),
                ('canal', models.CharField(db_index=True, default='whatsapp_edu', max_length=30)),
                ('facilitador_checkpoint', models.CharField(blank=True, default='', max_length=10)),
                ('regla_aplicada', models.CharField(blank=True, db_index=True, default='', max_length=60)),
                ('es_reto', models.BooleanField(blank=True, null=True)),
                ('modelo', models.CharField(blank=True, default='', max_length=60)),
                ('latencia_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('tokens_in', models.PositiveIntegerField(blank=True, null=True)),
                ('tokens_out', models.PositiveIntegerField(blank=True, null=True)),
                ('input_preview', models.TextField(blank=True, default='')),
                ('output_preview', models.TextField(blank=True, default='')),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('cliente', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='eventos_ia',
                    to='core.cliente',
                )),
                ('curso', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='eventos_ia',
                    to='core.curso',
                )),
                ('estudiante', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='eventos_ia',
                    to='core.estudiante',
                )),
                ('modulo', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='eventos_ia',
                    to='core.modulo',
                )),
            ],
            options={
                'verbose_name': 'Evento IA',
                'verbose_name_plural': 'Eventos IA',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='eventoia',
            index=models.Index(fields=['-created_at', 'tipo'], name='core_evento_created_tipo_idx'),
        ),
        migrations.AddIndex(
            model_name='eventoia',
            index=models.Index(fields=['trace_id', 'created_at'], name='core_evento_trace_created_idx'),
        ),
    ]
