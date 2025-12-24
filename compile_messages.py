#!/usr/bin/env python
"""Compilar archivos .po a .mo sin necesidad de gettext."""
import os
import struct
import array

def generate_mo(po_filename, mo_filename):
    """Compilar un archivo .po a .mo usando Python puro."""
    from email.parser import HeaderParser
    
    # Leer el archivo .po
    translations = {}
    metadata = {}
    
    with open(po_filename, 'rb') as f:
        lines = f.readlines()
    
    i = 0
    current_msgid = None
    current_msgstr = None
    parsing_metadata = True
    
    while i < len(lines):
        line = lines[i].decode('utf-8', errors='ignore').strip()
        i += 1
        
        if line.startswith('msgid "'):
            if current_msgid is not None and current_msgstr is not None:
                if current_msgid:
                    translations[current_msgid] = current_msgstr
                else:
                    metadata_str = current_msgstr
            current_msgid = line[7:-1]
            current_msgstr = None
        elif line.startswith('msgstr "'):
            current_msgstr = line[8:-1]
        elif line.startswith('"') and line.endswith('"'):
            if current_msgstr is not None:
                current_msgstr += line[1:-1]
            elif current_msgid is not None:
                current_msgid += line[1:-1]
    
    # Guardar la última entrada
    if current_msgid is not None and current_msgstr is not None:
        if current_msgid:
            translations[current_msgid] = current_msgstr
    
    # Generar archivo .mo
    # Formato MO: https://www.gnu.org/software/gettext/manual/gettext.html#MO-Files
    keys = sorted(translations.keys())
    offsets = []
    ids = b''
    strs = b''
    
    for key in keys:
        if key:  # Ignorar claves vacías
            key_bytes = key.encode('utf-8')
            value_bytes = translations[key].encode('utf-8')
            
            offsets.append((len(ids), len(key_bytes), len(strs), len(value_bytes)))
            ids += key_bytes + b'\x00'
            strs += value_bytes + b'\x00'
    
    # Header del archivo .mo
    keyoffset = 7 * 4 + 16 * len(keys)
    valueoffset = keyoffset + len(ids)
    koffsets = []
    voffsets = []
    
    for k_off, k_len, v_off, v_len in offsets:
        koffsets.append((k_len, keyoffset + k_off))
        voffsets.append((v_len, valueoffset + v_off))
    
    # Escribir archivo .mo
    with open(mo_filename, 'wb') as f:
        # Magic number y versión
        f.write(struct.pack('Iiiiiii', 
                           0xde120495,  # Magic
                           0,           # Version
                           len(keys),   # Número de strings
                           7 * 4,       # Offset de tabla de índices original
                           7 * 4 + len(keys) * 8,  # Offset de tabla de índices traducida
                           0,           # Tamaño tabla hash
                           0))          # Offset tabla hash
        
        # Tabla de índices original
        for k_len, k_off in koffsets:
            f.write(struct.pack('ii', k_len, k_off))
        
        # Tabla de índices traducida
        for v_len, v_off in voffsets:
            f.write(struct.pack('ii', v_len, v_off))
        
        # Strings originales
        f.write(ids)
        # Strings traducidos
        f.write(strs)

if __name__ == '__main__':
    locale_dir = 'locale/es_CO/LC_MESSAGES'
    po_file = os.path.join(locale_dir, 'django.po')
    mo_file = os.path.join(locale_dir, 'django.mo')
    
    if os.path.exists(po_file):
        try:
            generate_mo(po_file, mo_file)
            print(f"✅ Archivo {mo_file} compilado correctamente.")
        except Exception as e:
            print(f"❌ Error compilando: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ Archivo {po_file} no encontrado.")
