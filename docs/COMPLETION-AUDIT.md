# Completion audit — 2026-10-10

The active objective remains **build out the rest of the subtitle to speech lab**.
The original G0–G4 delivery has technical evidence and an explicit frontier plan.
The broader goal is not achieved: speech performance, real-media dialogue fit and
episode-length listener comfort are still unverified. Unblinded excerpt preferences
now favor Bella for fitted short dialogue and Heart for normal-speed conversation. Tests cannot substitute for those verdicts.

## Original delivery requirements

| Requirement | Current evidence | Verdict / limit |
|---|---|---|
| 1. Inspect starter and run unchanged smoke | Initial 12-test smoke; current 35-test suite; original adapters and parsing retained | Proven technical path. Optional integrations skip on bare stdlib |
| 2. Read-only host inventory | Initial/current doctor; Torch XPU properties and xpu-smi discovery/stats | Actual discrete/integrated names and memory visible. No device index assumed; runtime/PCI identity correlation remains a prerequisite for GPU allocation |
| 3. Append-only initial receipt | Initial receipt commands, versions, outcomes and SHA256SUMS | Sealed; checksum reverified. Machine details remain ignored/local |
| 4. Supplied synthetic WAV fixtures and parser edge case | SRT/VTT/ASS tone renders; VTT metadata regression; SHA/duration/overflow checks | Proven. Two fresh tone renders have identical mix and all stem hashes. Tone is not speech |
| 5. Separate sources/engines/composition; simple CLI/no-dependency tests | Cue/Engine/WAV boundaries, native optional CPU engines, wav-dir and HTTP import evidence | Proven technical architecture; no serving/orchestration platform introduced |
| 6. Real local English WAV | Isolated maintained Piper HTTP and native Piper/Kokoro; supplied fixture and authored 20 cues | Ran on host. Operator confirmed successful playback and preliminary intelligibility |
| 7. Engine/model/resource/timing/pronunciation record | Cold startup/demo, 3 warmups + 10 measured sets, latency/RTF, CPU/RSS/affinity, stem/mix/overrun evidence | Quantitative record present. Detailed pronunciation and episode comfort remain unscored; operator raised pacing/style concerns |
| 8. Current Fish/lighter-candidate research and host enumeration | Saved upstream model/install/license sources; actual Torch XPU enumeration; Kokoro CPU trial | Documented vs ran-on-host separated. Fish inference is unproven; cards remain occupied |
| 9. Same-20-cue bounded A/B protocol | Corpus identical across both CPU arms; 3 complete warmups + 10 complete measurements each, actual latency/resources | Technical comparison verified. Sequential runs, casting differs; unblinded excerpt preferences recorded; no blinded quality or speaker-consistency verdict. Fish smoke deferred for capacity |
| 10. Authorized source first; OCR optional; no protections bypass | Synthetic embedded-track extraction plus public CC BY Sintel captions; maintained parser crosscheck and caption bounds audit | Caption acquisition ran. Matching full-film video unavailable; trailer/caption mismatch rejected. OCR/live platform capture deferred |
| Required plan, receipts, handoff, small local commits | FRONTIER-PLAN.md, HANDOFF.md, five sealed experiment receipts and small commits | Present and verified locally; no pushes |

## Broader gates

- **G5:** manual stock-voice casting and an explicit capped tempo experiment run.
  Original audio survives and residual overflow remains visible. Character identity,
  speaker consistency and episode comfort remain unscored. Page-relative phrasing/style
  preferences are recorded, with the first-syllable concern not explicitly resolved.
- **G6:** all 20 authored embedded captions extract exactly; 26 licensed real-caption
  cues agree with pysubs2 and synthesize. This does not prove real-film completeness
  or dialogue alignment. Available video and captions belong to different cuts.
- **G7:** authored offline MP4 has play/pause/seek/caption evidence, including a
  nonzero video origin and decoded AAC waveform checks. Real-media playback,
  Japanese soundtrack separation and external live-browser synchronization remain
  unproven. Soundtrack recovery and automatic casting are separate research gates.

## Work that can unlock the next experiment

1. Listener identifies an awkward cue/gap or gives phrasing/speaker-consistency
   judgments on the existing short comparisons. Then change one voice/performance
   lever on the same words/windows and measure overflow without trimming.
2. A matching authorized video/caption pair becomes available. Audit bounds and
   source identity, synthesize, mux and verify browser clock plus human playback.
3. Safe GPU capacity becomes available without changing unrelated workloads.
   Re-enumerate runtime identity and PCI mapping, then run the bounded Fish smoke.

Current complete listening links:

- Four-cue timing comparison: http://127.0.0.1:18576/short-review/index.html
- Real-caption conversation: http://127.0.0.1:18579/review/index.html

Adding engines, fixtures or a larger framework without resolving these evidence
requirements would not prove the requested outcome. The repeated blockers are
unassessed performance/comfort, missing matching authorized media, and unavailable
Fish GPU capacity. The active goal must not be marked complete from this audit.
