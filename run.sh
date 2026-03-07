#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [[ -d "venv" ]]; then
  # shellcheck source=/dev/null
  source "venv/bin/activate"
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: Debes definir la variable de entorno OPENAI_API_KEY para usar el asistente RAG." >&2
  exit 1
fi

streamlit run app.py

