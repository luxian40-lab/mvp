from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class AddIndexConcurrentlySiPostgres(AddIndexConcurrently):
    """En SQLite (tests locales) no existe CONCURRENTLY: índice normal."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == 'postgresql':
            return super().database_forwards(app_label, schema_editor, from_state, to_state)
        return migrations.AddIndex.database_forwards(self, app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == 'postgresql':
            return super().database_backwards(app_label, schema_editor, from_state, to_state)
        return migrations.AddIndex.database_backwards(self, app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('core', '0188_sesion_y_log_por_linea'),
    ]

    operations = [
        AddIndexConcurrentlySiPostgres(
            model_name='whatsapplog',
            index=models.Index(fields=['phone_id'], name='core_wlog_phone_id_idx'),
        ),
    ]
