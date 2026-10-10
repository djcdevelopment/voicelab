# Subtitle Lab handoff — 2026-10-10

Work was performed in the existing session checkout. `/work/subtitle` was empty;
no second repo was created. Local commits preserve the starter, a metadata parser
repair/20-cue CPU bench, and this research handoff. Nothing was pushed.

## Reproduce

From the checkout root:

```bash
./scripts/smoke.sh
PYTHONPATH=src python3 -m subtitle_lab doctor --out output/doctor-new.json
UV_CACHE_DIR=$PWD/.cache/uv uv venv --python 3.12 .venv
UV_CACHE_DIR=$PWD/.cache/uv uv pip install --python .venv/bin/python -r output/RECEIPTS/initial-20261010-01/packages.txt
.venv/bin/python -m piper.download_voices en_US-lessac-medium --data-dir models/piper
# Existing env already contains this symlink; create only in a fresh env:
.venv/bin/python -c 'import pathlib,imageio_ffmpeg; pathlib.Path(".venv/bin/ffmpeg").symlink_to(imageio_ffmpeg.get_ffmpeg_exe())'
.venv/bin/python scripts/bench_piper.py output/RECEIPTS/piper-new-unique
PYTHONPATH=src python3 -m subtitle_lab validate output/RECEIPTS/piper-new-unique/measured-01
```

The bench refuses existing output directories, checks port 18573 is free, starts
only its own CPU Piper on loopback, and terminates its own server in finally.
It records startup, a cold five-cue demo, three full-set warmups and ten measured
20-cue renders. FFmpeg is isolated via imageio-ffmpeg; no system packages changed.
The benchmark currently leaves ONNX's default thread pool intact; two OpenMP
threads do not bound ONNX Runtime CPU use. Address this before longer runs.

## Evidence and limits

Receipt: `output/RECEIPTS/initial-20261010-01/` (local, ignored, sealed with SHA256).
Listen first to `piper/cold-demo/dub.wav` and `piper/measured-01/dub.wav`.
Individual unmodified TTS stems are under each run's `stems/`.

- Original 12-test smoke passed; 13 tests pass after preventing WebVTT metadata
  timing examples from becoming speech. SRT/VTT/ASS tone/checksum paths pass.
- Piper 1.8.0, ONNX Runtime 1.31.0, Lessac medium produced actual speech WAVs.
  22,050 Hz stems are converted to the harness's 24,000 Hz mono PCM16 mix.
- Startup 1.006 s; cold demo generation 0.227 s, pipeline 0.521 s for 13.816 s
  utterances. These are startup/first-run measurements, not cleared OS disk caches.
- Ten warm sets: mean generation RTF 0.02097, mean pipeline RTF 0.04476,
  median pipeline 1.551 s. Every warm run has 3–4 overruns >250 ms; no next-start
  overlaps >250 ms or mixed clipping. Cold demo has one overrun and overlap.
- Observed server peak RSS 269.43 MiB; server CPU 470.11 core-seconds across
  about 21.64 observed seconds. This is substantial CPU use, not a two-core run.
  Client/mixer CPU and peak combined RSS were not measured. Piper used CPU;
  no incremental Piper VRAM allocation was measured or needed.
- PyTorch XPU enumeration succeeded read-only in the existing environment;
  exact local names, memory, versions, filters and separate xpu-smi iGPU evidence
  are in doctor JSON and GPU files. No torch package was added to the speech env.
- Two existing GPU serving workloads occupy most discrete memory. Fish was not
  installed or run. Upstream XPU instructions are not a B70 compatibility proof.
- No listening was performed: pronunciation, intelligibility and acting remain
  unassessed. G3 functional audio path works; full qualitative gate is pending.
- Character casting, duration fitting, source separation, soundtrack mix,
  caption acquisition and synchronized playback remain unimplemented.

Exact next experiment: operator listens and labels the 20 cues, then constrain
only a new Piper process to two CPU cores and rerun this benchmark in a fresh
receipt. Proceed to Kokoro CPU A/B if listening establishes a useful baseline.
See FRONTIER-PLAN.md for the complete protocol and three acceptance gates.
