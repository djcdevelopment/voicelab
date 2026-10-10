# Speech backends — verified integration leads

## Piper (working adapter, server NOT included)

The maintained OHF-Voice Piper implementation documents an HTTP service:

- Source: https://github.com/OHF-Voice/piper1-gpl
- HTTP API: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_HTTP.md
- CLI instructions: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md

In an isolated Python environment dedicated to Piper (not the host's existing model environment), the upstream pattern is:

```bash
python3 -m venv .venv-piper
.venv-piper/bin/python -m pip install 'piper-tts[http]'
.venv-piper/bin/python -m piper.download_voices en_US-lessac-medium --data-dir models/piper
.venv-piper/bin/python -m piper.http_server -m en_US-lessac-medium \
  --data-dir models/piper --host 127.0.0.1 --port 5000
```

Verify exact CLI flags for the installed Piper version before running. Audio request (from a second terminal):

```bash
curl --fail --silent --show-error -X POST \
  -H 'Content-Type: application/json' -d '{"text":"Hello from Subtitle Lab."}' \
  http://127.0.0.1:5000/synthesize -o /tmp/subtitle-piper-test.wav
```

Then use `--engine piper-http` as described in README. Piper is a **CPU baseline**, not necessarily the quality winner. One voice ≠ convincing anime character acting. The maintained code and model voices may have different licenses; verify before selecting voices.

## Native CPU backends (ran on host)

`piper-local` uses Piper 1.8.0/ONNX Runtime with explicit bounded worker settings;
`kokoro` uses Kokoro 0.9.4 with pinned local weights and stock voices. Both completed
three whole-set warmups and ten measured repetitions of the same 20 synthetic
cues. See [CPU comparison](CPU-VOICE-COMPARISON.md) for measurement scopes and
[handoff](HANDOFF.md) for runnable commands. Optional speech dependencies remain
in isolated repository environments; the standard-library smoke path is preserved.

Latest unblinded preferences favor Bella for fitted short synthetic dialogue and
Heart for normal-speed conversation, with no global default change. Voice identity,
words, windows and timing policy must be held fixed for a new targeted probe.
Detailed pronunciation, consistency and whole-episode comfort remain unscored.

## Fish Audio S2 Pro (research candidate; not implemented)

- Official implementation: https://github.com/fishaudio/fish-speech
- XPU install: https://github.com/fishaudio/fish-speech/blob/main/docs/en/install.md
- Local API: https://speech.fish.audio/server/
- Inference: https://speech.fish.audio/inference/
- Model: https://huggingface.co/fishaudio/s2-pro

Official Fish install docs specify **24 GB VRAM for inference** and include **Intel Arc XPU installation instructions** with PyTorch XPU nightly. This is **not proof** that every current B70 software configuration works or that 24 GB suffices with all cache/concurrency settings. Fish exposes local server `POST /v1/tts` and a client utility; investigate actual request and WAV decoding with the matching repository version. Do not assume its JSON API accepts a generic Piper-style payload or output format.

Recommended experiment: use a separate Python 3.12 env, one explicitly selected B70, a small set of English synthetic lines, and a bounded number of iterations; record actual OOMs, driver/runtime issues, speed and quality. If successful, add an engine adapter that writes the same cue-numbered WAVs. The existing `wav-dir` adapter works as an interim integration.

## Evaluation without vendor lock-in

Accept any TTS backend that can return **a WAV file per subtitle cue**. Evaluate lighter contenders if Fish's compile/KV-cache/driver compatibility costs outweigh audible improvements. Keep the orchestration layer model-agnostic; only expose model-specific options behind backend adapters.

## Important known bottleneck

Unlike subtitles, natural dialogue includes pauses, phrasing, emphasis, character voice consistency, and background audio. GPU speed alone cannot solve word/timestamp alignment or source-separation quality. Record both objective timing metrics and subjective listening judgments.
