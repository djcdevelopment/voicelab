# CPU voice feasibility comparison — 2026-10-10

Both engines generated real English dialogue from the same 20 synthetic cues,
with three complete-set warmups followed by ten measured repetitions. The
functional path passed. Operator feedback finds the played sample understandable, with concerns about pacing/style over a whole episode. Engine and sample coverage were not specified; no per-cue or numeric quality scores are recorded.

| Measured result | Piper / Lessac medium | Kokoro v1.0 / Heart + Michael |
|---|---:|---:|
| Mean generation RTF | 0.0316 | 0.2521 |
| Mean end-to-end RTF | 0.0440 | 0.2590 |
| Median 20-cue pipeline wall time | 1.532 s | 12.129 s |
| Median / p95 cue generation latency | 53.5 / 71 ms | 594 / 720 ms |
| Sum of utterance durations per set | 34.37–35.38 s | 46.70 s |
| Cues >250 ms past their window per set | 3–5 | 6 |
| Maximum cue overrun | 901 ms | 1025 ms |
| Next-start overlaps in measured sets | 0 | 0 |
| Mixed clipped samples | 0 | 0 |
| Observed peak RSS | 250.6 MiB server | 1928.6 MiB entire bench |
| Sampled CPU / observed wall span, full run | 27.22 / 21.17 s | 317.71 / 165.29 s |

RTF uses total utterance duration, not the 70.2-second timeline containing silence.
P95 uses nearest rank over 200 measured cue latencies. Piper latency includes
HTTP/WAV writing; Kokoro includes local G2P/model/WAV writing. End-to-end time
adds composition; Piper additionally uses FFmpeg resampling. RSS/CPU scopes
are different: Piper server excludes the client and FFmpeg; Kokoro includes
its client/mixer. CPU measurements exclude the first sampling interval and the
short final tail. These differences prevent a strict whole-system cost comparison.

The arms ran sequentially, Piper first, rather than interleaved. This is a
feasibility screen, not a controlled quality ranking. No synthesis errors or
retries occurred. Two selected Linux CPUs were shared with ordinary host work;
affinity did not reserve or isolate those CPUs. All sampled threads stayed in
the selected pair. Neither engine allocated a GPU.

Piper used 1.8.0 and ONNX Runtime 1.31.0. Kokoro used 0.9.4, Misaki 0.9.4,
CPU Torch 2.14.1, and pinned model revision
`f3ff3571791e39611d31c381e3a41a3af07b4987`. Odd cues use af_heart, even cues
am_michael at speed 1.0; the chosen casts are manual fixture assignments, not
inferred characters. Torch seed is 42 per cue. Piper's default stochastic noise
was retained; repeated durations vary. The single/two-voice difference is a
casting confound. Separate voice quality and speaker consistency require listening.

## CPU-bound result

A first taskset-only attempt failed: the leader reported a two-CPU affinity,
but the process consumed 419.47 core-seconds in 19.04 seconds. That exceeds a
two-core ceiling. ONNX worker affinity override is inferred from this observation;
worker masks were not sampled in that first attempt.

A small process-local shim now runs the maintained upstream Piper HTTP server
with two ONNX intra-op threads, one inter-op thread, sequential execution and
idle spinning disabled. Installed upstream files remain untouched. The final
runner audits the union of every server thread's affinity at 100 ms intervals
and fails if an escape is observed. Full-run server CPU fell from the earlier
470.11 core-seconds to 27.22, with similar median end-to-end wall time. These
are sequential host measurements, not a randomized causal estimate.

## Audio findings and listening

Kokoro had no out-of-range float samples before PCM conversion and no measured
stem saturation. Piper stems contained 265 PCM endpoint samples across 200
measured utterances. Installed Piper source peak-normalizes by default; reaching
a PCM endpoint therefore does not by itself prove damaging clipping. Mixed
clipping was zero for both. Operator feedback provides preliminary intelligibility evidence, but no engine attribution or full-cue coverage. Audible distortion, missing words, pronunciation, expression and voice consistency remain unscored; episode-length pacing/style is an explicit concern. Kokoro's G2P
fallback loaded and the runner rejected missing phonemes on alphabetic tokens;
that check does not substitute for listening or establish every word is correct.

Every original generated stem is retained. No audio was shortened to a subtitle
window. The 70.2-second timed tracks have intentional gaps. Kokoro's longer
speech and six >250 ms overruns mean timing remains a separate gate even if its
acting later receives higher listener scores.

Complete playback URLs, served only on the Linux workstation:

- Player with explicit controls: http://127.0.0.1:18574/
- Piper MP3: http://127.0.0.1:18574/A/track.mp3
- Kokoro MP3: http://127.0.0.1:18574/B/track.mp3
- Piper original WAV: http://127.0.0.1:18574/A/track.wav
- Kokoro original WAV: http://127.0.0.1:18574/B/track.wav
- Scoring sheet: http://127.0.0.1:18574/scores.csv

MP3s are convenience listening copies; measured artifacts are WAVs. A simple
standard-library static server serves only the listening folder. The player
names engines; use A/B files and the separate assignment key for blind scoring.
HTTP responses and WAV decoding were checked. Firefox requested the WAVs, but
operator confirmed successful audio playback from the explicit-control player. Operator found the sample understandable but questioned pacing/style for a whole episode; detailed ratings remain pending. A read-only audio
routing snapshot is retained locally. No system audio settings were changed.

Receipt: `output/RECEIPTS/cpu-ab-20261010-01/`, with commands, failed attempt,
model/package/source hashes, raw metrics, resource samples, all 42 manifest
validations, before/after smoke output, and a listening bundle. Earlier receipts
remain unchanged.

GO for a small phrasing/pause comparison informed by the preliminary listening feedback.
Keep Piper as the lightweight functional baseline and Kokoro as the two-voice
candidate. NO-GO for declaring a quality winner, auto-casting, live capture or
Fish loading while the discrete cards remain occupied.
