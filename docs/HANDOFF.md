# Subtitle Lab handoff — 2026-10-10, CPU voice slice

The existing session checkout remains the repo. No second repo was created and
nothing was pushed. Synthetic subtitle → real local speech → timed WAV works
with Piper and Kokoro. Listening quality and true dialogue timing remain pending.

## Listen using complete URLs

Open this player in Firefox on the Linux workstation and press Play:

**http://127.0.0.1:18574/**

Direct files:

- Piper MP3: http://127.0.0.1:18574/A/track.mp3
- Kokoro MP3: http://127.0.0.1:18574/B/track.mp3
- Piper original WAV: http://127.0.0.1:18574/A/track.wav
- Kokoro original WAV: http://127.0.0.1:18574/B/track.wav
- Listener scores (copy before editing): http://127.0.0.1:18574/scores.csv

The player is served by this session's Python static server. To restart it after
that process ends, run from the checkout root (use a free port if occupied):

```bash
python3 -m http.server 18574 --bind 127.0.0.1 --directory "$PWD/output/RECEIPTS/cpu-ab-20261010-01/listening"
```

Complete local paths for the measured tracks:

```text
/home/derek/work/subtitles/output/RECEIPTS/cpu-ab-20261010-01/piper-session-bounded/measured-01/dub.wav
/home/derek/work/subtitles/output/RECEIPTS/cpu-ab-20261010-01/kokoro/measured-01/render/dub.wav
```

Dialogue begins after 0.5 seconds; timeline gaps are intentional. MP3 listening
copies preserve the original measured WAVs. HTTP and decoder checks passed;
Direct WAV opening was initially reported problematic; the MP3 player with explicit controls was then confirmed to play audio successfully.
No workstation audio routing was changed.

## Reproduce the bounded benchmarks

From the checkout root, preserve the no-dependency path:

```bash
./scripts/smoke.sh
.venv/bin/python scripts/bench_piper.py output/RECEIPTS/piper-next-unique
.venv-kokoro/bin/python scripts/bench_kokoro.py output/RECEIPTS/kokoro-next-unique
```

Each runner refuses an existing destination and selects two CPUs from the current
allowed affinity. Override with `--cpus 4,5` only if that pair is allowed. Piper
starts only its own loopback HTTP server on 18573 and terminates it in finally.
Its process-local ONNX shim sets two intra-op workers, one inter-op worker,
sequential execution and no idle spinning. Both runners sample all worker masks
and reject observed affinity escape. No cgroups, drivers or existing services
were changed.

Piper environment/voice installation was recorded in the initial handoff receipt;
FFmpeg is provided only inside `.venv` by imageio-ffmpeg. Packages are pinned
locally in `output/RECEIPTS/cpu-ab-20261010-01/piper-packages.txt`.
For Kokoro, the successful isolated installation was:

```bash
UV_CACHE_DIR=$PWD/.cache/uv uv venv --python 3.12 .venv-kokoro
UV_CACHE_DIR=$PWD/.cache/uv uv pip install --python .venv-kokoro/bin/python torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
UV_CACHE_DIR=$PWD/.cache/uv uv pip install --python .venv-kokoro/bin/python kokoro==0.9.4 soundfile==0.14.0 espeakng-loader==0.2.4
UV_CACHE_DIR=$PWD/.cache/uv uv pip install --python .venv-kokoro/bin/python https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
HF_HOME=$PWD/.cache/huggingface HF_HUB_DISABLE_IMPLICIT_TOKEN=1 .venv-kokoro/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('hexgrad/Kokoro-82M',
    revision='f3ff3571791e39611d31c381e3a41a3af07b4987', token=False,
    local_dir='models/kokoro', allow_patterns=['config.json', 'kokoro-v1_0.pth',
    'voices/af_heart.pt', 'voices/am_michael.pt', 'README.md', 'VOICES.md', 'LICENSE*'])
PY
```

The complete resolved versions are in `kokoro-packages-final.txt` in the receipt;
the commands above pin principal packages but are not a full dependency lock.
No system espeak installation was needed: upstream Misaki uses espeakng-loader.
The benchmark enforces offline model access after preparation and explicitly
selects CPU. Stock voices alternate on odd/even cues at speed 1.0, seed 42 per cue.
It writes external WAV stems then uses the existing wav-dir adapter. Its render
manifest generation time is **import time**, not Kokoro synthesis time; use
`synthesis.json` and `benchmark.json` for actual generation latency/RTF.

## What the evidence says

All 13 tests pass before and after changes. Both engines completed 3 whole-set
warmups plus 10 measured 20-cue runs without synthesis failure or retries.
All 42 manifests in the new receipt validate, including the failed resource-bound
attempt's valid audio outputs. The failure was resource discipline, not synthesis.

Piper: mean generation RTF 0.0316, median set wall 1.532 s, observed server RSS
250.6 MiB, full-run server CPU 27.22 s. The old default used 470.11 core-seconds;
a taskset-only attempt still used 419.47, so it is explicitly recorded as failed.

Kokoro: mean generation RTF 0.2521, median set wall 12.129 s, observed full-process
RSS 1928.6 MiB. The 20 cues contain 46.70 seconds of generated speech, versus
Piper's roughly 35 seconds. Kokoro has six >250 ms overruns per measured set;
Piper has three to five. Neither measured timed mix clips or overlaps the next
cue start. Piper PCM endpoint values occur after upstream peak normalization;
that alone does not prove audible distortion. No audio was cut to fit.

These were sequential feasibility runs with different measurement scopes and
single/two-voice casting, not a blinded quality verdict. Pronunciation, expression,
intelligibility and speaker continuity remain unassessed. Fish, subtitle capture,
character inference, duration fitting, source separation and synchronized
playback remain unproven/unimplemented.

Full evidence: `output/RECEIPTS/cpu-ab-20261010-01/` (sealed locally); original
receipt `output/RECEIPTS/initial-20261010-01/` remains unchanged.
See `docs/CPU-VOICE-COMPARISON.md` for the metric definitions and limitations.

Exact next experiment: listen to all 20 cues and annotate
intelligibility/pronunciation/acting and two-voice consistency. If useful speech
passes, compare Kokoro speed 1.0 versus 1.15 on the same cues in a fresh receipt;
measure every duration change and assess degradation, with no truncation. Do not
advance to live acquisition or claim convincing dubbing until listening passes.
