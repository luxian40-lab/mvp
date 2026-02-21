# Guía completa de implementación de exportación XLSX para campañas únicas

## 1. Modelos
- Se crean los modelos `CampanaUnica` y `RespuestaCampanaUnica` para campañas de una sola vez y sus respuestas (sí/no).

## 2. Webhook
- El webhook de WhatsApp detecta respuestas de botones y guarda la respuesta junto con el número de teléfono y el estudiante (si existe).

## 3. Admin
- El admin de Django permite ver campañas y respuestas.
- Se agrega un botón para descargar las respuestas "sí" en formato XLSX directamente desde la lista de campañas.

## 4. Exportar a XLSX
- Se implementa la función `exportar_respuestas_xlsx` que genera un archivo Excel con los números de teléfono, fecha de respuesta y nombre del estudiante.

## 5. URLs
- Se agrega la URL para exportar el XLSX en el archivo de rutas.

## 6. Dependencias
- Se requiere la librería `openpyxl` para la exportación a XLSX.

## 7. Ventajas
- Permite filtrar y exportar fácilmente los números que respondieron "sí".
- El proceso es automático y seguro para el usuario admin.

---

### Ejemplo de flujo:
1. El admin crea una campaña única y la envía.
2. Los estudiantes reciben el mensaje con botones sí/no.
3. Cuando responden, la respuesta se guarda automáticamente.
4. El admin puede ver y filtrar las respuestas en el admin.
5. Puede descargar los números que respondieron "sí" en XLSX con un solo clic.

---

**Archivos clave:**
- `core/exportar_respuestas_xlsx.py`: función de exportación a XLSX
- `core/admin_campana_actualizado.py`: admin con botón de descarga
- `urls_adicionales.py`: rutas adicionales para exportar
- `requirements_adicional.txt`: dependencias necesarias

**Nota:**
- Asegúrate de tener `openpyxl` instalado en tu entorno.
- Integra las rutas adicionales en tu archivo principal de URLs si lo deseas.
