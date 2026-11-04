#!/bin/sh
# Run the local browser compiler with the installed ESP-IDF Python environment.
set -eu
studio_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "${RNBO_STUDIO_PYTHON:-}" ]; then
  studio_python=$RNBO_STUDIO_PYTHON
else
  studio_python=""
  for studio_candidate in "$HOME"/.espressif/python_env/idf5.5_py*_env/bin/python; do
    if [ -x "$studio_candidate" ]; then studio_python=$studio_candidate; fi
  done
  if [ -z "$studio_python" ]; then studio_python=python3; fi
fi
exec "$studio_python" "$studio_root/host/studio/server.py" "$@"
