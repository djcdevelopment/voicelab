# Architecture — stages, contracts, and exclusions

## Current vertical slice (implemented)

```text
Local subtitle file (SRT / VTT / ASS)
              │
              ▼
      subtitle_lab.subtitles
      Cue(index, start_ms, end_ms, text, speaker?)
              │
              ▼
      interchangeable Engine
   ┌──────────┼─────────────┐
   ▼          ▼             ▼
 tone       piper-http     wav-dir
          piper-local     kokoro (CPU)
 (beep)    (real TTS)     (external model)
   └──────────┼─────────────┘
              ▼
       utterance WAVs
              │
              ▼
      PCM16 mono normalization
      and timeline summing
              │
              ▼
 dub.wav + stems/ + receipt + manifest + timing diagnostics
```

All engines obey `Engine.synthesize(cue, destination_path)`. Current backend selection is CLI-based and manual. Stems are standalone files; any model can be evaluated by writing its utterances to 0001.wav, 0002.wav, etc.

## Implemented local source and playback boundaries

Optional `media.py` borrows FFmpeg for text-track extraction and muxing, and
PyAV for stream/timestamp inventory. Local text captions feed the same parser;
there is no platform downloader. A manual JSON voice plan maps source speakers
or cue numbers to stock voices; unknown/unused assignments fail explicitly.

The render manifest v2 includes a source snapshot, normalized cue hashes,
backend/model provenance, original and fitted durations, cue gaps/overlaps,
amplitude activity and per-stage latency. Existing v1 receipts still validate.
Explicit capped `atempo` produces separate processed WAVs and leaves originals
unchanged. Amplitude activity is not word alignment or a true dialogue boundary.

`compose` verifies video origin and speech extent before muxing, refusing to
truncate utterances. Explicit `--clock video` in extraction and composition
subtracts first-frame PTS from both timelines; raw source captions and rounding
error remain recorded. Extracted caption identity and clock metadata survive in
render snapshots. Composition rejects different source media/clock modes, and
extraction rejects captions preceding the first frame instead of clipping them. The optional background is an explicitly supplied WAV;
original source audio is discarded. Native video controls and VTT use one media
clock. Werkzeug conditional responses support browser seeking; the plain Python
file server failed this experiment. `compare` makes same-corpus listening copies
and optional excerpts that retain every selected utterance and the full WAV.
These are local diagnostic pages, with no app or scheduling framework.

## Future source adapters (NOT implemented)

1. **Accessible timed subtitles:** source-provided SRT/VTT/ASS or other authorized caption access. Best for accurate timing; no OCR noise.
2. **OCR from visible frames:** operator-supplied screenshot series or permitted local capture of the browser content. Track text changes, line persistence, bounding boxes, confidence, frame times, and duplicate suppression. Avoid reading browser tokens, cookies, or protected streams.
3. **Live subtitle observation:** events with monotonic timestamps and wall-clock/media-clock mapping; buffering and seeking/reconciliation. Live TTS will require prefetch or predictable slack.

Suggested adapter event schema (proposal, not yet wired):

```json
{
  "version": 1,
  "kind": "subtitle_observation",
  "observed_at_monotonic_ms": 12043,
  "media_start_ms": 10000,
  "media_end_ms": 12700,
  "text": "A test line.",
  "source": "operator-supplied-screenshot-ocr",
  "confidence": 0.98,
  "frame_hash": "sha256:..."
}
```

Do not assume captured-frame timestamps are equivalent to subtitle start/end times: they are observation times with potential delay. This distinction must remain measurable.

## Voice research integration

- Start with a functioning local, non-expressive single-voice TTS baseline.
- Evaluate Fish S2 Pro separately on actual Arc B70 XPU. Record cold start, warm throughput, quality and failure cases, and memory use. Avoid altering existing production inference envs.
- Preserve voice casting as a pluggable mapping: `character_id` → `model/reference/speaker`.
- Original Japanese audio emotion → optional emotion annotation is exploratory; preserve uncertainty and manual correction.
- For natural dubbing, separately address translation length, cue boundaries, word alignment, overlapping characters, pauses, performance direction, and original soundtrack separation. None are solved just by fast generation.

## Timing metrics

For each cue, record source start/end, generated speech duration, generation latency, overlap with the next cue, and overrun past the cue's end. Strong offline evaluation should later add forced alignment, voice continuity, prosody, listener rating, and source-audio preservation.

**Important:** A subtitle window is not a true dialogue window. The next gated improvement should demonstrate and measure that distinction, not hide it with silent truncation.

## Track/mix limitations

Current output is 24000 Hz mono PCM16 with simple additive overlap. Original source audio is discarded during optional offline muxing. A separately prepared permissioned background WAV can be mixed with measured clipping; original music/effects are not recovered automatically. For a later soundtrack-aware dub, evaluate source separation on permitted local media and collect objective/listener evidence. Do not assume center-channel reduction eliminates dialogue.
