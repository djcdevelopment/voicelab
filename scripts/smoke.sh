#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONPATH="$(pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m unittest discover -s tests -v
mkdir -p output
BASE="$(mktemp -d "$(pwd)/output/smoke-XXXXXX")"
python3 -m subtitle_lab inspect samples/demo.srt --out "$BASE/inspect.json"
python3 -m subtitle_lab render samples/demo.srt --engine tone --out "$BASE/render"
python3 -m subtitle_lab validate "$BASE/render"
echo "PASS: smoke outputs in $BASE"
