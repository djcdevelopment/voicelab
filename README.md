# Voice Lab

A local text-to-speech tool and a lab for tuning voices for narration and podcasts.
Paste text, hear it spoken, adjust the delivery, and keep the settings that work.

Voice Lab runs on Linux with a .NET 10 / Blazor browser interface and Python speech
engines. Speech runs locally on CPU. This is a personal R&D tool with a working
paste-and-listen workflow.

## What works today

- Paste English text in the browser or pipe it through the CLI.
- Generate speech with Kokoro (Heart, Bella, Michael) or Piper (Lessac).
- Adjust synthesis speed and added pauses between paragraphs.
- Pin a result for A/B listening, record a preference, and save named presets.
- Replay, seek, download WAVs, and revisit local history.
- Cancel generation and recover interrupted requests after an app restart.
- Keep reproducible receipts with source text, settings, model/package versions,
  timings, original audio, and checksums.

The repository also contains the earlier subtitle experiment pipeline: SRT/VTT/ASS
parsing, manual voice casting, duration fitting, and offline synchronized playback.

## Run the app

Prerequisites: Linux, Python 3, `curl`, and separately prepared speech environments
and models. The setup script installs the pinned .NET SDK inside this checkout;
**it does not install speech packages or download voices**.

```bash
git clone https://github.com/djcdevelopment/voicelab.git
cd voicelab
./scripts/setup-voice-lab.sh
./scripts/voice-lab.sh
```

Open **http://127.0.0.1:18581/**. Use `--port 18583` to choose another port.
Ctrl+C stops the app and its active speech worker.

The current app expects these local resources:

| Engine | Python environment | Model files |
| --- | --- | --- |
| Kokoro | `.venv-kokoro/bin/python` | `models/kokoro/` with config, weights, and stock voice files |
| Piper | `.venv/bin/python` plus `.venv/bin/ffmpeg` | `models/piper/en_US-lessac-medium.onnx` and its `.onnx.json` |

Speech setup is currently manual. See the [handoff](docs/HANDOFF.md) for recorded
CPU setup/version details and [backend notes](docs/TTS-BACKENDS.md) for integration
background. Unavailable engines are disabled in the app. Environments, model
weights, and generated output are not included in the repository.

## Use it

1. Paste an excerpt and start with **Kokoro / Heart / 1.00× / 250 ms**.
2. Click **Generate speech** or press **Ctrl+Enter**, then press Play.
3. **Pin as A**, change one setting, generate again, and compare.
4. Optionally add a listening note. Use a result's **Use settings** button before
   saving those controls as a preset.

Blank lines separate paragraphs. The paragraph-gap control adds silence between
them while preserving natural pauses and complete speech. Editing controls during
generation prepares the next request; it does not alter the active result.

## Paste from the CLI

With the Kokoro environment and model prepared, run from the repository root:

```bash
export PYTHONPATH="$PWD/src"
.venv-kokoro/bin/python -m subtitle_lab speak \
  --text-file - --engine kokoro --voice af_heart --speed 1.0 \
  --paragraph-pause-ms 250 --out output/RECEIPTS/my-text-01
```

Paste your text, then press **Ctrl+D** on an empty line. Open
`output/RECEIPTS/my-text-01/speech.wav` to listen. Replace `--text-file -` with a
UTF-8 file path to read from a file. Choose a new output directory for each run.

```bash
python3 -m subtitle_lab validate output/RECEIPTS/my-text-01
```

## Local data and current limits

Generated text/audio and immutable run receipts live under `output/RECEIPTS/`.
Presets and listening notes live under `output/voice-lab/`. These folders, models,
virtual environments, and caches are git-ignored. The browser draft is stored in
the current tab's session storage; history and presets survive app restarts.

The first version supports up to **5,000 characters per request**, one generation
at a time, and complete generation before playback. Each request loads a fresh
model worker, so startup contributes to the wait. Listening preferences are
subjective; automated checks do not establish voice quality. GPU inference,
expressive emotion controls, voice cloning, long-document streaming, and live
subtitle capture remain future experiments.

## Development and verification

```bash
./scripts/smoke.sh
```

The smoke path uses only Python's standard library; optional integrations skip
when their dependencies are absent. The current implementation has 38 tests,
with all 38 passing in the prepared optional environment. Chromium checks also
cover the browser workflow and real Heart, Bella, and Piper generation.

See [operator instructions](docs/OPERATOR.md) for browser verification commands,
[architecture](docs/ARCHITECTURE.md) for the implementation, and the
[handoff](docs/HANDOFF.md) for measured results and remaining work.

## License

Project code is licensed under the [MIT License](LICENSE). Bundled Bootstrap
includes its own [MIT notice](app/VoiceLab/wwwroot/lib/bootstrap/LICENSE).
Speech engines and model weights retain their upstream licenses.
