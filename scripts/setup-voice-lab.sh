#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p .cache/dotnet .cache/dotnet-home .cache/nuget
sdk_version="$(python3 -c 'import json; print(json.load(open("global.json"))["sdk"]["version"])')"
curl -fsSL https://dot.net/v1/dotnet-install.sh -o .cache/dotnet-install.sh
bash .cache/dotnet-install.sh --version "$sdk_version" --install-dir "$PWD/.cache/dotnet" --no-path
printf 'SDK installed locally. Start with ./scripts/voice-lab.sh\n'
