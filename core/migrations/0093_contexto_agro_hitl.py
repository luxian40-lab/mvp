# Parte 3 + 4 — Contexto agronómico Nati y cola HITL Knowledge Studio

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0092_evento_ia'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContextoAgroSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cultivo', models.CharField(blank=True, default='', max_length=80)),
                ('etapa', models.CharField(blank=True, default='', help_text='Ej: floración, desarrollo', max_length=80)),
                ('region', models.CharField(blank=True, default='', help_text='Departamento o zona', max_length=120)),
                ('municipio', models.CharField(blank=True, default='', max_length=80)),
                ('clima', models.CharField(blank=True, default='', help_text='Ej: alta humedad, sequía', max_length=80)),
                ('problema', models.CharField(blank=True, default='', help_text='Plaga, enfermedad, nutrición', max_length=200)),
                ('notas', models.TextField(blank=True, default='')),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sesion', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='contexto_agro', to='core.sesioncomercial', verbose_name='Sesión comercial')),
            ],
            options={
                'verbose_name': 'Contexto agronómico (Nati)',
                'verbose_name_plural': 'Contextos agronómicos (Nati)',
            },
        ),
        migrations.CreateModel(
            name='ConversacionRAGCandidata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefono', models.CharField(db_index=True, max_length=30)),
                ('trace_id', models.UUIDField(blank=True, db_index=True, null=True)),
                ('pregunta', models.TextField()),
                ('respuesta_nati', models.TextField()),
                ('respuesta_revisada', models.TextField(blank=True, default='')),
                ('contexto_agro', models.JSONField(blank=True, default=dict)),
                ('chunks_rag', models.JSONField(blank=True, default=list)),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente revisión'), ('aprobada', 'Aprobada (sin publicar)'), ('rechazada', 'Rechazada'), ('publicada', 'Publicada en RAG')], db_index=True, default='pendiente', max_length=20)),
                ('notas_revisor', models.TextField(blank=True, default='')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('fecha_revision', models.DateTimeField(blank=True, null=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='candidatas_rag', to='core.cliente')),
                ('documento_rag', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='candidatas_origen', to='core.documentoragcomercial')),
                ('revisado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='candidatas_rag_revisadas', to=settings.AUTH_USER_MODEL)),
                ('sesion', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='candidatas_rag', to='core.sesioncomercial')),
            ],
            options={
                'verbose_name': 'Candidata RAG (HITL)',
                'verbose_name_plural': 'Candidatas RAG (HITL)',
                'ordering': ['-fecha_creacion'],
            },
        ),
    ]
