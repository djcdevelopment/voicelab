# Pilot experiment matrix — initial proposal

| Arm | Generation method | Backend hardware | Outcome needed | Status |
|---|---|---|---|---|
| A | Synthetic tones | CPU | Validate cue timestamps, overlap, checksums and report | Working starter |
| B | Single English voice | Piper HTTP, likely CPU | Evaluate real intelligible dialogue and timing deltas | Adapter ready; external server required |
| C | Expressive voice | Fish S2 Pro candidate | Validate Intel Arc XPU functionality and audio quality | Untested |
| D | Second expressive contender | Arc or CPU, verified compatible | Compare quality/RTF/complexity against C | To select |
| E | Two manual character voices | Any proven backend | Test continuity, overlapping dialogue and audience rating | Planned |
| F | Subtitle OCR vs soft track | Accessible samples | Compare completeness, timing lag, text error | Planned |

For B–D, hold a fixed synthetic 20-line English corpus across all engines. Include:
- 5 short (<1.5 seconds window) cues
- 5 average spoken sentences
- 5 emotional/fast-paced lines
- 5 overlapping / scene-transition cases

Every arm must have an actual WAV, a timed manifest, environment/weights IDs, a short listener note, and a clear pass/fail. Aggregate both mean and tail latency; always distinguish cold versus warm generation. Use a separate memo for licensing and available reference-voice permissions before experiments involving recognizable people's voices.
