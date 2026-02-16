# Generated manually - Add cedula field (Step 2: populate and make unique)

from django.db import migrations, models


def populate_cedulas(apps, schema_editor):
    """Asignar cédulas únicas a estudiantes existentes"""
    Estudiante = apps.get_model('core', 'Estudiante')
    for i, estudiante in enumerate(Estudiante.objects.filter(cedula__isnull=True), start=1):
        estudiante.cedula = f"TEMP{i:06d}"  # TEMP000001, TEMP000002, etc.
        estudiante.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_add_cedula_nullable'),
    ]

    operations = [
        # Paso 2: Poblar cédulas temporales
        migrations.RunPython(populate_cedulas, migrations.RunPython.noop),
        
        # Paso 3: Hacer el campo unique y no nullable
        migrations.AlterField(
            model_name='estudiante',
            name='cedula',
            field=models.CharField(
                max_length=20,
                unique=True,
                help_text='Número de identificación único (cédula de ciudadanía)',
                verbose_name='Cédula'
            ),
        ),
        
        # Agregar índice
        migrations.AddIndex(
            model_name='estudiante',
            index=models.Index(fields=['cedula'], name='core_estudia_cedula_idx'),
        ),
        
        # Actualizar verbose names
        migrations.AlterField(
            model_name='estudiante',
            name='nombre',
            field=models.CharField(max_length=100, verbose_name='Nombre Completo'),
        ),
        migrations.AlterField(
            model_name='estudiante',
            name='telefono',
            field=models.CharField(max_length=20, unique=True, verbose_name='Teléfono WhatsApp'),
        ),
        migrations.AlterField(
            model_name='estudiante',
            name='activo',
            field=models.BooleanField(default=True, verbose_name='Activo'),
        ),
        migrations.AlterField(
            model_name='estudiante',
            name='fecha_registro',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro'),
        ),
    ]
