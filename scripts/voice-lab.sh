#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export DOTNET_ROOT="$PWD/.cache/dotnet"
export DOTNET_CLI_HOME="$PWD/.cache/dotnet-home"
export NUGET_PACKAGES="$PWD/.cache/nuget"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_GENERATE_ASPNET_CERTIFICATE=false
export XDG_CACHE_HOME="$PWD/.cache"
port=18581
diagnostics=false
while (($#)); do
    case "$1" in
        --port) port="${2:?--port needs a number}"; shift 2 ;;
        --diagnostics) diagnostics=true; shift ;;
        *) echo "Usage: $0 [--port 18581] [--diagnostics]" >&2; exit 2 ;;
    esac
done
if [[ ! "$port" =~ ^[0-9]+$ ]] || ((port < 1024 || port > 65535)); then
    echo 'Choose a port from 1024 to 65535.' >&2; exit 2
fi
if [[ ! -x "$DOTNET_ROOT/dotnet" ]]; then
    echo 'Run ./scripts/setup-voice-lab.sh first to install the pinned repo-local .NET SDK.' >&2
    exit 1
fi
export PATH="$DOTNET_ROOT:$PATH"
dotnet build app/VoiceLab --nologo -v quiet
printf 'Voice Lab: http://127.0.0.1:%s/ — Ctrl+C stops this app.\n' "$port"
exec dotnet run --project app/VoiceLab --no-build --no-launch-profile -- \
    --urls "http://127.0.0.1:$port" --repo-root "$PWD" --diagnostics "$diagnostics"
