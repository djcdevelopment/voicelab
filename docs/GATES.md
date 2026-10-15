# Experiment gates and stop/go criteria

Gate status below distinguishes running synthetic evidence from listening and
real-source evidence. Detailed receipts remain local and ignored by git.

| Gate | Observed evidence | Remaining acceptance gap |
|---|---|---|
| G0 | Read-only inventory, actual XPU enumeration, occupied cards recorded | Recheck capacity before any GPU allocation |
| G1 | SRT/VTT/ASS smoke, metadata regression and clock tests | Richer subtitle formats only when encountered |
| G2 | Tone/WAV composition, checksums, no-truncation tests | Tone is not speech evidence |
| G3 | Piper and Kokoro CPU; 3 warmups + 10 measured sets; preliminary intelligibility feedback | Pronunciation, acting and episode comfort remain unscored |
| G4 | Upstream Fish XPU research; actual host enumeration | Fish inference blocked by occupied cards; compatibility unproven |
| G5 | Two manually assigned Kokoro voices; capped tempo fit retains originals | Bella/Heart excerpt preferences recorded; consistency and episode comfort unscored; character inference absent |
| G6 | Authored video text track: all 20 cues exact, then real speech synthesis; explicit nonzero-origin mapping tested | 26 published CC BY captions parsed/synthesized; matching full-film video unavailable; browser/OCR not implemented |
| G7 | Synthetic offline MP4: shared clock, play/pause, seeks both ways and active captions pass Chromium automation | Human Firefox video/audio review; real soundtrack separation and live sync absent |

Voice Lab adds a plain-text UI alongside these subtitle gates. Its CPU browser
workflow, A/B audio controls, presets/history, cancellation and real Heart/Bella/
Piper generation have Chromium evidence; human listening quality remains unscored.
Details and limitations are in the current handoff.

The latest suite has 38 tests (optional media/HTTP integrations skip on a bare
stdlib host). Unchanged smoke remains runnable without installing speech models.

## First cold-builder work session

1. Run `./scripts/smoke.sh` unmodified. Preserve test and generated receipt.
2. Run `subtitle_lab doctor` with local GPU/tool data; identify actual Intel discrete device indices. Record existing inference-server pressure (read-only) and a safe resource allocation.
3. Compare Piper HTTP, existing vLLM/other serving capabilities (only if relevant), Fish S2 XPU, and at least one lighter speech-generation contender. Cite upstream docs and exact model license/hardware constraints.
4. Prove one **real English voice** by serving Piper or reusing an already-running compatible local TTS endpoint, if obtainable without disrupting current services. Document failures rather than claiming success without samples.
5. Generate a synthetic sample run, analyze `manifest.json`, and identify the highest-impact next timing problem.
6. Propose G4/G5 experiments with a small reproducible matrix: speech quality, RTF, first-audio latency, clip/window overrun, speaker consistency, VRAM, CPU consumption, stability.
7. Hand back a concise go/no-go recommendation for next work; no UI, agent orchestration system, or multi-machine deployment without evidence.

## Minimum empirical measures for TTS engine comparisons

- Exact engine/model version, weights/hash/license, voice identity, driver/torch version.
- Device index AND device name; record iGPU/discrete mapping and VRAM observed.
- 3 warmups + 10 timed samples of equal text, separately report cold and warmed numbers.
- Wall-clock generation time, audio duration, real-time factor (`generation_seconds / audio_seconds`), first audio latency where measurable, failure and retry counts.
- Peak/observed RAM and GPU memory if available, batching/concurrency, CPU overhead.
- Relative subjective naturalness, consistency, expression, and pronunciation on **the same** labeled test lines (clearly mark subjective judgments).
- End-to-end temporal defects: duration overrun, overlap with next cue, unexplained silence, audible truncation, clipping.

## Failure and scope discipline

- Never silently trim speech to subtitle window.
- Do not claim two separate GPU memories act as a single 64 GB heap.
- Do not benchmark while changing clocks, drivers, serving versions, or unrelated model loads without recording changes.
- If XPU model fails, preserve exception and minimal reproducer; try one bounded remediation per experiment instead of a broad framework rewrite.
- No downloading protected media or bypassing DRM/stream restrictions to reach G6.
