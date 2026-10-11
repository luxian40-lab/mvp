#!/bin/bash
# .ebignore empaqueta el arbol de trabajo. En Windows esos .sh llegan con CR.
# bash trata el CR como parte de la opcion y web.service muere:
#   set: pipefail\r: invalid option name
# status 2/INVALIDARGUMENT, antes de Django. Corre en staging, antes del Procfile.
cd /var/app/staging || exit 0
for f in scripts/run_web.sh scripts/run_worker.sh scripts/run_worker_rag.sh scripts/run_beat.sh Procfile Procfile.ai; do
  if [ -f "$f" ]; then
    sed -i 's/\r$//' "$f"
  fi
done
