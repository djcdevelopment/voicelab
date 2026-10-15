# Operator cheatsheet

## Voice Lab: paste, listen, tune

From the checkout root:

```bash
# First setup only: installs the pinned .NET SDK inside .cache/dotnet.
./scripts/setup-voice-lab.sh
# Build and start the app. Ctrl+C cancels its worker and stops the app.
./scripts/voice-lab.sh
```

Open **http://127.0.0.1:18581/**. If that port belongs to another application,
use `./scripts/voice-lab.sh --port 18583`. Only one Voice Lab instance may write
this repo's library at once. The launcher leaves other lab services alone.

1. Paste up to 5,000 characters of English text. Blank lines separate paragraphs;
   single line breaks within a paragraph become spaces for speech.
2. Start with Kokoro / Heart / 1.00× / 250 ms. Click **Generate speech** or press
   **Ctrl+Enter**, then press Play. Generation finishes before audio playback.
3. **Pin as A**, change a voice, speed, or paragraph gap, then generate B. Playing
   either result pauses the other. Gap adds silence; it does not remove natural
   pauses. Speed is synthesis rate, not the audio player's speed.
4. Optionally record a preference and listening note. These are subjective,
   unblinded comparisons; different source text is explicitly labeled.
5. Use a result's **Use settings** button and save a named preset. Presets contain
   settings only. **Restore text & settings** also restores that result's input.

The editor stays editable during synthesis; changes apply to the next Generate.
Cancel affects the single active request across all tabs. Closing/reloading a
tab does not cancel a request. Completed results and presets survive app restarts;
the editor draft survives reloads in the same tab. A second tab shares history
and the active request, but has its own editor.

Installed choices are Heart, Bella, Michael and Piper Lessac. Unavailable engines
are disabled with the missing prerequisites shown. No model is downloaded or
substituted automatically. Fish, expressive emotion controls, subtitle timing,
and long-document streaming are outside this app's first slice.

Every request stages under `output/voice-lab/work/` and is sealed into a new
`output/RECEIPTS/text-<timestamp>-<id>/`. `run.json` summarizes the app run and
hashes its files. `speech/manifest.json` contains exact model/package provenance,
spoken paragraphs, and measured audio data. Originals, full speech, and logs are
retained. Presets and later notes live separately in `output/voice-lab/library.json`.
Generated text and audio remain local and git-ignored. Receipt directories are
immutable; do not edit them to change a preference. There is no automatic cleanup.

The UI's generation wait includes process startup. Details show model startup,
speech synthesis, duration, and generation/speech ratio separately. A fresh worker
loads the model for every request; the first load can take longer. Signal metrics
such as saturated samples are not audio-quality judgments. Human listening remains
the quality check.

### Paste from a terminal

```bash
export PYTHONPATH="$PWD/src"
export PATH="$PWD/.venv/bin:$PATH"
.venv-kokoro/bin/python -m subtitle_lab speak \
  --text-file - --engine kokoro --voice af_heart --speed 1.0 \
  --paragraph-pause-ms 250 --out output/RECEIPTS/my-next-text
# Paste text, then press Ctrl+D on an empty line to finish input.
python3 -m subtitle_lab validate output/RECEIPTS/my-next-text
```

Open `output/RECEIPTS/my-next-text/speech.wav` in your player. For a file, replace
`--text-file -` with its UTF-8 path. For Piper, use `.venv/bin/python`,
`--engine piper-local`, and omit `--voice`. Each output path must be new.
Direct CLI receipts validate normally but are not added to the browser's app-run
history. `--engine tone` is the dependency-free plumbing check, not speech.

### Verify the app

```bash
./scripts/smoke.sh
# In a separate terminal; exposes a clearly labeled tone engine for this check.
./scripts/voice-lab.sh --diagnostics
# Use a NEW receipt directory each time.
.venv-browser/bin/python scripts/verify_playback.py --voice-lab --real-speech \
  --url http://127.0.0.1:18581/ --out output/RECEIPTS/my-next-browser-check
```

The browser checker uses the existing isolated Playwright/Chromium setup. It
generates synthetic examples and an explicitly labeled automation preset/note.
Audio is muted: PASS proves playback mechanics, storage, and setting propagation,
not intelligibility or preference. Omit `--real-speech` for the tone workflow
(cancellation still checks a Kokoro startup). Stop the diagnostic app and relaunch
normally for everyday use.

## Subtitle CLI

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
