#!/usr/bin/env bash
# Create qwen3.5:9b-32k — the 9B model with a pinned 32k context window,
# mirroring the existing qwen3.5:4b-32k. Run locally (needs the Ollama CLI).
set -euo pipefail

BASE="qwen3.5:9b"
TARGET="qwen3.5:9b-32k"
NUM_CTX=32768
DIR="$(cd "$(dirname "$0")" && pwd)"
MODELFILE="$DIR/qwen3.5-9b-32k.Modelfile"

echo "▶ Checking for base model $BASE …"
if ! ollama list | awk '{print $1}' | grep -qx "$BASE"; then
  echo "  base not found — pulling $BASE (this downloads several GB)…"
  ollama pull "$BASE"
else
  echo "  ✓ $BASE already present"
fi

# Optional: inherit the 4b-32k's template/params so the 9b behaves identically
# apart from size. If that model exists, copy its non-FROM/non-num_ctx lines in.
if ollama list | awk '{print $1}' | grep -qx "qwen3.5:4b-32k"; then
  echo "▶ Mirroring settings from qwen3.5:4b-32k …"
  {
    echo "FROM $BASE"
    ollama show --modelfile qwen3.5:4b-32k \
      | grep -vE '^\s*(FROM|#|PARAMETER\s+num_ctx)\b' || true
    echo "PARAMETER num_ctx $NUM_CTX"
  } > "$MODELFILE.merged"
  BUILD="$MODELFILE.merged"
else
  BUILD="$MODELFILE"
fi

echo "▶ Creating $TARGET (num_ctx=$NUM_CTX) …"
ollama create "$TARGET" -f "$BUILD"

echo "▶ Verifying …"
ollama show "$TARGET" | grep -iE 'context|num_ctx|parameters' || true
echo "✓ Done. Select '$TARGET' in Odysseus (Settings → default model)."
