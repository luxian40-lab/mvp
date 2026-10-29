#!/bin/bash
# eb setenv vuelve a extraer el bundle en staging con el Procfile completo y no corre .platform/hooks/.
# Sin este paso la caja de IA arranca el worker general y un segundo beat.
# Tampoco corre hooks/predeploy/04_lineas_unix.sh: el Procfile generado se limpia de CR aquí.
set -e
bash .platform/hooks/prebuild/01_eki_procfile_role.sh
if [ -f Procfile ]; then
  sed -i 's/\r$//' Procfile
fi
