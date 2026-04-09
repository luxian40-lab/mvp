from django.db import migrations


class Migration(migrations.Migration):

	dependencies = [
		("core", "0071_fase23_empleabilidad"),
	]

	operations = [
		migrations.RenameIndex(
			model_name="documentoragcomercial",
			new_name="core_docume_cliente_527ab8_idx",
			old_name="core_docume_cliente_a7a17d_idx",
		),
		migrations.RenameIndex(
			model_name="misionempleabilidad",
			new_name="core_mision_estudia_cad59a_idx",
			old_name="core_misione_estudia_2c88c4_idx",
		),
		migrations.RenameIndex(
			model_name="misionempleabilidad",
			new_name="core_mision_cliente_7bc163_idx",
			old_name="core_misione_cliente_7a9074_idx",
		),
		migrations.RenameIndex(
			model_name="misionempleabilidad",
			new_name="core_mision_aliado__efd6e8_idx",
			old_name="core_misione_aliado__ceb898_idx",
		),
		migrations.RenameIndex(
			model_name="misionempleabilidad",
			new_name="core_mision_cliente_30f0d6_idx",
			old_name="core_misione_cliente_9f4f77_idx",
		),
	]
