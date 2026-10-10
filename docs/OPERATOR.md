# Operator cheatsheet

From the existing checkout root:

```bash
export PYTHONPATH="$PWD/src"
./scripts/smoke.sh
python3 -m subtitle_lab doctor --out output/doctor-20261010.json
python3 -m subtitle_lab inspect samples/demo.vtt
python3 -m subtitle_lab render samples/demo.ass --engine tone --out output/ass-test-01
python3 -m subtitle_lab validate output/ass-test-01
```

`doctor` only reads local properties and installed tool versions. It may not see XPU unless torch is already installed in the current environment. If `output/doctor-20261010.json` exists, choose a new receipt name.

To connect a real local Piper server, read `docs/TTS-BACKENDS.md`. To audition the resulting track, `ffplay -autoexit output/<run>/dub.wav` or open `dub.wav` in your audio player.

For external voice models, generate WAV clips named `0001.wav` through `NNNN.wav` and run `--engine wav-dir --wav-dir PATH`. `ffmpeg` is required if clip sample rates or channels differ from 24k mono 16-bit.

**If capture from Crunchyroll fails:** avoid spiraling into browser DRM or authentication internals. First establish the same pipeline with user-created or permissioned local subtitles, then use a permitted on-screen screenshot/OCR proof or accessible caption text source. Capture/stream/download capability is **not** implied by a functional TTS engine.

End each engineering session with a dated markdown receipt containing environment, passed/failed checks, synthesized example location, remaining limitation, and next bounded action.

## Audit a video/caption pair before synthesizing

```bash
export PATH="$PWD/.venv/bin:$PATH"
.venv/bin/python -m subtitle_lab audit-captions local_media/authorized.mkv local_media/captions.srt --out output/caption-audit-new.json
```

An out-of-bounds cue produces FAIL and exit 1. This checks windows only; a PASS
does not establish that the caption file belongs to the same edition or matches
spoken words. For nonzero video origins, choose clocks explicitly as documented
in [HANDOFF](HANDOFF.md). Existing diagnostic players and complete URLs are also
listed there; keep original audio and use new output folders for every experiment.
