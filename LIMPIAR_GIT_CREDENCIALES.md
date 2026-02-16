# 🚨 LIMPIEZA DE CREDENCIALES - HISTORIAL GIT

**OBJETIVO:** Eliminar credenciales expuestas del historial de Git

## Archivos comprometidos identificados:

1. `verificar_twilio_sandbox.py` - Commits: d57ec929, 7543305f
2. `DEPLOY_RENDER.md` - Commit: 1442d806
3. `GUIA_META_WHATSAPP.md` - Commit: 1442d806  
4. `GUIA_TWILIO_IA.md` - Commit: 1442d806
5. `PLAN_ESTA_SEMANA.md` - Commit: 1442d806

**Credencial expuesta:** `TWILIO_ACCOUNT_SID_REDACTED`

---

## ⚠️ ADVERTENCIA

**NO EJECUTAR** hasta haber rotado credenciales de Twilio primero.

Una vez rotadas las credenciales, esta limpieza evitará que alguien use las viejas del historial.

---

## MÉTODO 1: git-filter-repo (RECOMENDADO)

```bash
# 1. Instalar git-filter-repo
pip install git-filter-repo

# 2. Crear archivo de reemplazo
cat > replacements.txt << EOF
TU_TWILIO_SID_AQUI==>TWILIO_ACCOUNT_SID_REDACTED
EOF

# 3. Ejecutar filtro
cd c:\Users\luxia\OneDrive\Escritorio\eki_mvp
git filter-repo --replace-text replacements.txt --force

# 4. Force push (PELIGROSO - reescribe historial)
git push origin --force --all
git push origin --force --tags
```

---

## MÉTODO 2: BFG Repo-Cleaner (ALTERNATIVO)

```bash
# 1. Descargar BFG
# https://rtyley.github.io/bfg-repo-cleaner/

# 2. Crear archivo de reemplazos
echo "TU_TWILIO_SID_AQUI" > passwords.txt

# 3. Limpiar repo
java -jar bfg.jar --replace-text passwords.txt c:\Users\luxia\OneDrive\Escritorio\eki_mvp

# 4. Limpiar refs
cd c:\Users\luxia\OneDrive\Escritorio\eki_mvp
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 5. Force push
git push origin --force --all
```

---

## MÉTODO 3: Eliminar archivos completamente (MÁS SEGURO)

Si los archivos NO son necesarios, eliminarlos del historial:

```bash
cd c:\Users\luxia\OneDrive\Escritorio\eki_mvp

# Eliminar archivo del historial completo
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch verificar_twilio_sandbox.py DEPLOY_RENDER.md GUIA_META_WHATSAPP.md GUIA_TWILIO_IA.md PLAN_ESTA_SEMANA.md" \
  --prune-empty --tag-name-filter cat -- --all

# Limpiar
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push
git push origin --force --all
```

---

## VERIFICACIÓN POST-LIMPIEZA

```bash
# Buscar credencial en historial completo
git log --all -S "TU_TWILIO_SID_AQUI" --source --oneline

# Si devuelve VACÍO = ÉXITO ✅
# Si devuelve resultados = FALLÓ ❌ (intentar de nuevo)
```

---

## ⚠️ IMPORTANTE

- **Backup antes de ejecutar:** `git clone mvp mvp-backup`
- **Notificar al equipo:** Force push reescribe historial
- **Todos deben re-clonar:** `git clone` después del push
- **No hacer durante deploy activo**

---

## DESPUÉS DE LIMPIEZA

1. ✅ Verificar credenciales no están en GitHub
2. ✅ Todos los desarrolladores re-clonan repo
3. ✅ Actualizar `.gitignore` para prevenir futuros errores
4. ✅ Configurar pre-commit hooks para detectar secretos
