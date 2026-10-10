# Experiment matrix — evidence checked 2026-10-10

| Arm | Method | Running evidence | Acceptance gap |
|---|---|---|---|
| A | Synthetic tones, CPU | SRT/VTT/ASS renders, hashes, deterministic repeat, timing regressions | Diagnostic audio only |
| B | Piper HTTP/native CPU | Real English WAV; cold demo; 3 warmups + 10 measured 20-cue sets; resource limits audited | Detailed listener quality/pronunciation |
| C | Fish S2 Pro on Arc | Upstream XPU/model/license research and actual host enumeration | Safe capacity and actual inference; compatibility unproven |
| D | Kokoro CPU | 3 warmups + 10 measured 20-cue sets; two stock voices; native CLI and external WAV path | Acting, listener comfort and comparison verdict |
| E | Manual casting / timing probe | Explicit voice plan; baseline, speed 0.95, capped 1.15 tempo; original WAVs retained | Speaker continuity and naturalness verdict |
| F | Authorized subtitle source | Exact 20-cue synthetic extraction; 26 CC BY real captions match pysubs2; wrong video cut rejected | Matching authorized real video; OCR optional and deferred |
| G | Offline shared-clock playback | Native MP4 play/pause/seek/captions; explicit video-origin mapping; first/last decoded audio correlation | Human review on real matching media; soundtrack separation/live sync separate |

The measured CPU arms use the frozen `samples/dialogue20.srt`, identical normalized
words/windows, three complete warmups and ten complete measurements. The old
proposal for five overlapping source cues was not the measured corpus: the frozen
20-cue fixture has no source-window overlaps. Supplied shorter fixtures do produce
actual speech overlap, recorded separately. Do not change the benchmark corpus to
make prior claims fit a proposal.

The two CPU arms ran sequentially, with one Piper voice and two Kokoro voices.
Their resource scopes differ. They establish feasibility rather than a blinded
quality ranking. Exact versions, source/model hashes, cold/warm metrics and all
failures remain in ignored receipts. No quality scores are fabricated.

Rate/tempo and published-caption probes are single-run experiments, not repeated
benchmarks. Use the same words/windows for each lever, preserve originals, and
collect listener judgments before interpreting timing improvements as better acting.
