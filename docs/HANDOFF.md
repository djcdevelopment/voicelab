# Subtitle Lab handoff — offline pipeline slice

Real local CPU speech, explicit manual casting and an offline caption-to-video
chain work on authored fixtures. Preliminary operator feedback: understandable,
but pacing/style may be unsuitable for an episode. No engine winner is inferred.

Complete links on this workstation:

- Short pacing comparison: http://127.0.0.1:18576/short-review/index.html
- Full three-arm comparison: http://127.0.0.1:18576/review/index.html
- Extracted text track → Piper → synchronized video: http://127.0.0.1:18576/playback-from-track/index.html
- Kokoro synchronized video: http://127.0.0.1:18576/playback/index.html

These use an authored moving test pattern and tone background, not anime footage.
The range-capable loopback server is running for review. Restart only this lab's
server when needed; choose another free port if occupied:

```bash
export PYTHONPATH="$PWD/src"
export PATH="$PWD/.venv/bin:$PATH"
.venv/bin/python -m subtitle_lab serve output/RECEIPTS/bench-build-20261010-01 --port 18576
```

## Reproduce in new output directories

Run from the repo root. Existing models/envs are isolated here; package versions
and hashes are in local receipts. The plain smoke does not need model packages.

```bash
./scripts/smoke.sh
export PYTHONPATH="$PWD/src"
export PATH="$PWD/.venv/bin:$PATH"
.venv/bin/python -m subtitle_lab render samples/dialogue20.srt --engine piper-local --model models/piper/en_US-lessac-medium.onnx --threads 2 --out output/piper-new
.venv-kokoro/bin/python -m subtitle_lab render samples/dialogue20.srt --engine kokoro --model-dir models/kokoro --cast samples/cast-dialogue20.json --threads 2 --out output/kokoro-new
.venv-kokoro/bin/python -m subtitle_lab render samples/dialogue20.srt --engine kokoro --model-dir models/kokoro --cast samples/cast-dialogue20.json --speed 0.95 --threads 2 --out output/kokoro-slower-new
.venv/bin/python -m subtitle_lab render samples/dialogue20.srt --engine wav-dir --wav-dir output/kokoro-new/stems --fit-max-speedup 1.15 --out output/kokoro-fit-new
.venv/bin/python -m subtitle_lab compare output/kokoro-new output/kokoro-slower-new output/kokoro-fit-new --first-cues 4 --out output/listening-new
```

For an operator-authorized local video with an accessible embedded text track:

```bash
.venv/bin/python -m subtitle_lab probe-media local_media/authorized.mkv
.venv/bin/python -m subtitle_lab extract local_media/authorized.mkv --subtitle-index 0 --out output/captions-new
.venv/bin/python -m subtitle_lab render output/captions-new/subtitles.srt --engine piper-local --model models/piper/en_US-lessac-medium.onnx --threads 2 --out output/speech-new
.venv/bin/python -m subtitle_lab compose local_media/authorized.mkv output/speech-new --out output/playback-new
.venv/bin/python -m subtitle_lab validate output/speech-new
.venv/bin/python -m subtitle_lab validate-media output/playback-new
.venv/bin/python -m subtitle_lab serve output/playback-new --port 18577
```

Then open http://127.0.0.1:18577/ . Default video is stream-copied; explicit
`--transcode-video` enables bounded CPU H.264 conversion. Original audio is
removed. Optional `--background` requires an already prepared WAV bed; source
separation is not performed. Speech beyond the video fails explicitly instead of truncating audio. For nonzero
video timestamps, add `--clock video` to both extraction and composition; captions
are explicitly rebased to the first video frame and the raw SRT is retained.
The default source clock still refuses nonzero origins. Extraction metadata is
carried into renders, and mismatched source hashes or clock modes fail. Bitmap captions have no OCR fallback.

## Verified scope and limits

35 tests pass with optional dependencies; unchanged bare smoke passes with optional
integrations skipped. All eight render/media manifests in the latest receipt
validate. Twenty extracted authored cues match text and milliseconds exactly.
Headless Chromium checks play advancement, pause holding time, forward/backward
seek, active captions and resumed frame/media clock. This muted automated check
is not a listening judgment or Firefox verification.

Original Kokoro: 46.70 seconds of speech, six >250 ms overruns. Speed 0.95:
48.70 seconds, seven overruns. Capped 1.15 tempo fit: 44.655 seconds, five overruns,
ten altered cues, original stems retained. No next-cue overlaps above 250 ms or
mixed clipping in these runs. These are single-run timing probes, not a repeated
benchmark. The prior 3+10 CPU benchmarks remain unchanged below.

The basic static server failed seeking, resetting time to zero. Maintained
Werkzeug HTTP Range handling fixed the observed issue; failed browser checks
remain in the receipt. Source separation, automatic casting, true dialogue
alignment, expressive Fish inference, OCR/browser acquisition and live sync
remain open. No unrelated service or GPU allocation was changed.

Exact next experiment: listen to the short matched comparison, identify a cue or
gap responsible for the pacing/style concern, and change one voice/performance
setting on that same four-cue corpus. Record listener phrasing/comfort and measured
original duration, overflow and gaps. Do not declare episode readiness from RTF.

## Explicit source clock evidence

The `clock-map-20261010-01` receipt proves a synthetic video starting at 5 seconds,
with original audio starting at zero. Explicit video-clock extraction restores all
20 authored cue timestamps exactly; muxed video and audio both start at zero and
last 72 seconds. Source identity/clock mismatch and pre-video captions are rejected.
Browser play/pause/forward/backward seek and caption checks pass. This is synthetic
container timing evidence, not a real anime dialogue-alignment result.

Player: http://127.0.0.1:18578/playback-bound/index.html

```bash
.venv/bin/python -m subtitle_lab extract local_media/authorized.mkv --clock video --out output/mapped-captions-new
.venv/bin/python -m subtitle_lab render output/mapped-captions-new/subtitles.srt --engine piper-local --model models/piper/en_US-lessac-medium.onnx --threads 2 --out output/mapped-speech-new
.venv/bin/python -m subtitle_lab compose local_media/authorized.mkv output/mapped-speech-new --clock video --out output/mapped-playback-new
```

## Permissioned caption-source trial

Public Sintel English captions were acquired from Xiph with their CC BY 3.0
copyright notice. All 26 cues agree exactly with pysubs2 1.9.0 on text/timing;
Piper and Kokoro synthesized every cue. One-shot results: Piper 39.846 s speech,
zero >250 ms overruns; Kokoro 54.275 s, two. Neither has >250 ms next-start overlap
or mixed clipping. These results have no repeated benchmark or listener verdict.

Conversation comparison (first 12 cues, about 49 seconds):
http://127.0.0.1:18579/review/index.html

The W3C video is a 52.208-second trailer; the Xiph captions belong to the full
film and begin at 107.250 seconds. The new bounds audit rejects all 26 cues for
that trailer (exit 1), so these files were not composed. Full-film download routes
checked this slice returned 403, or 404 for a nonexistent W3C movie file. Those
are recorded blockers, not a reason to bypass access controls or invent offsets.

Before synthesis on a supplied video/caption pair:

```bash
.venv/bin/python -m subtitle_lab audit-captions local_media/authorized.mkv local_media/captions.srt --clock source --out output/caption-audit-new.json
```

Use `--clock video` only for captions already rebased to the first video frame.
PASS proves timestamps fall within video bounds; it does not verify caption words,
completeness, edition matching or dialogue alignment. The receipt remains local at
`output/RECEIPTS/permissioned-source-20261010-01/`. No source subtitles/media were
committed. Attribution, URLs, checksums and unsuccessful source requests are kept
there. Current next source experiment requires a matching authorized full film;
keep the real-caption audio comparison for listener judgment in the meantime.

## Earlier bounded CPU benchmark handoff

# Subtitle Lab handoff — 2026-10-10, CPU voice slice

The existing session checkout remains the repo. No second repo was created and
nothing was pushed. Synthetic subtitle → real local speech → timed WAV works
with Piper and Kokoro. Operator found the sample understandable but raised episode-length pacing/style concerns. Detailed quality ratings and true dialogue timing remain pending.

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

The earlier CPU slice passed 13 tests before and after changes. Both engines completed 3 whole-set
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
single/two-voice casting, not a blinded quality verdict. Preliminary operator intelligibility feedback is positive, with pacing/style concerns. Engine attribution and cue coverage are unspecified; pronunciation, expression and speaker continuity remain unscored. Fish, subtitle capture,
character inference and source separation remain unproven/unimplemented. Later timing and offline playback evidence is described above.

Full evidence: `output/RECEIPTS/cpu-ab-20261010-01/` (sealed locally); original
receipt `output/RECEIPTS/initial-20261010-01/` remains unchanged.
See `docs/CPU-VOICE-COMPARISON.md` for the metric definitions and limitations.

Exact next experiment: identify four awkward utterances or gaps in the playable
tracks, then run a matched four-cue probe with identical text and placements,
changing one stock voice or one rate setting at a time. Rate intelligibility,
phrasing and episode-listening comfort, and measure overflow/gap changes. Choose
the lever from the marked defect: speeding speech up can enlarge the gaps and
should not be presumed to improve pacing. Preserve unmodified baselines and do
not trim audio. The played engine was not specified, so the present feedback
cannot choose a model winner. No whole episode or live acquisition yet.

## Latest operator listening feedback

Operator: “those are getting better.” This is positive perceived improvement, with
sample/engine/variant attribution still unspecified. It does not establish a model
winner or whole-episode comfort. Baselines remain unchanged. Clarify the preferred
comparison/variant before choosing a single phrasing/pause lever for the next pass.
New feedback receipt: `output/RECEIPTS/listening-feedback-20261010-01/`.
