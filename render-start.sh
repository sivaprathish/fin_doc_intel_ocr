#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
OCR_DIR="$PROJECT_DIR/.runtime/tesseract"

mkdir -p "$OCR_DIR"

tar -xzf "$PROJECT_DIR/tools/tesseract-linux-amd64.tar.gz" \
    -C "$OCR_DIR"

export TESSERACT_CMD="$OCR_DIR/bin/tesseract"
export OMP_THREAD_LIMIT=1
export PYTHONPATH="$PROJECT_DIR/backend:${PYTHONPATH:-}"

"$TESSERACT_CMD" --version
"$TESSERACT_CMD" --list-langs

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1