# Subtitle Lab frontier plan — 2026-10-10

G0–G2 have running evidence. G3 has real local speech and timing/resource evidence,
but intelligibility, pronunciation and acting quality await operator listening.
G4 now has a Kokoro CPU feasibility result; Fish XPU remains a plan, not a host compatibility result.
Local machine details remain in ignored receipts `initial-20261010-01` and `cpu-ab-20261010-01`.

The extracted checkout is the session workspace; the requested `/work/subtitle`
was empty. Work stayed in the existing checkout. No existing service was changed.
The original smoke passed 12 tests; the repaired smoke passes 13. SRT, VTT and ASS
synthetic tone renders validate. WebVTT NOTE/STYLE/REGION metadata is skipped;
a regression test prevents a NOTE timing example becoming speech.

Piper 1.8.0 with en_US-lessac-medium generated the supplied five-cue fixture and
20 authored dialogue cues. Three whole-set warmups preceded ten measured
whole-set repetitions. Mean HTTP generation RTF was 0.02097; mean pipeline RTF
including normalization/mixing was 0.04476. Median pipeline wall time was 1.551 s
for roughly 34–35 s of utterances. Every measured set had 3–4 window overruns
above 250 ms; none overlapped the next start above that threshold. The supplied
fixture did have one such overlap. No mixed clipping was observed. Speed does
not establish a convincing performance or correct dialogue windows.

Architecture remains file source → normalized Cue → Engine → WAV normalization
→ timestamped mix. HTTP and cue-numbered WAV imports share the same mixer;
zero-dependency CLI/tests remain runnable. No new serving framework is needed.
Keep original stems, measure overflow, and never silently cut or shorten speech.

| Candidate | Evidence and expressive potential | Speakers/timing | Resources and friction | License/fallback |
|---|---|---|---|---|
| OHF Piper | Ran on host; plain voice, listening pending | One chosen voice; upstream speaker IDs and length_scale; no hard duration guarantee | CPU baseline; isolated ONNX runtime. Fast wall time but default ONNX threading used substantial aggregate CPU | GPL-3.0 implementation; each voice has separate provenance. Lessac card links a research dataset agreement, not a universal voice grant. Keep local; review before distribution |
| Kokoro-82M | Ran on host CPU with two stock voices; acting/listening unassessed | Alternate Heart/Michael cues, speed 1.0; no exact duration or inferred identity | Two-core mean generation RTF 0.2521; observed bench RSS 1928.6 MiB. Isolated Torch/Misaki/espeakng-loader; six >250 ms overruns per set | Apache-2.0 weights; integrated through wav-dir; Piper fallback |
| Fish S2 Pro | Upstream inline prosody/emotion and multi-speaker support; strongest expressive research lead | Reference-controlled speakers and instruction tags; strict cue-duration control unproven | Upstream 24 GB inference VRAM and XPU nightly installation route. Host cards occupied; no inference attempted. Compiler/runtime compatibility remains unproven | Fish Audio Research License permits research/noncommercial use subject to terms; separate commercial license. No cloud fallback |

Sources checked this session: [Piper HTTP](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_HTTP.md),
[Lessac card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/lessac/medium/MODEL_CARD),
[Kokoro usage](https://github.com/hexgrad/kokoro),
[Kokoro weights](https://huggingface.co/hexgrad/Kokoro-82M),
[Fish installation](https://github.com/fishaudio/fish-speech/blob/main/docs/en/install.md),
[Fish model](https://huggingface.co/fishaudio/s2-pro),
[Fish license](https://huggingface.co/fishaudio/s2-pro/blob/main/LICENSE.md).
Source snapshots and checksums are local. Vendor quality/speed claims are not
host measurements. No model-memory pooling is assumed.

## Latest CPU slice

The follow-up completed Piper CPU bounding and a Kokoro feasibility comparison.
A taskset-only Piper attempt failed its resource bound and is preserved. Explicit
ONNX worker/thread/spinning settings reduced server CPU to 27.22 core-seconds;
all sampled worker masks stayed within two selected CPUs. Piper mean generation
RTF was 0.0316; Kokoro was 0.2521. Both completed three warmups and ten measured
whole-set repetitions, with no synthesis errors. Kokoro spoke longer (46.70 s
versus about 35 s) and had six >250 ms window overruns versus Piper's three to
five. No next-start overlap or mixed clipping in measured sets. Timing remains
unsolved. CPU/RSS measurement scopes differ and runs were sequential; this is
not a quality ranking. See `docs/CPU-VOICE-COMPARISON.md` for definitions.

Listening player with complete URLs: http://127.0.0.1:18574/ . It offers MP3
listening copies and original WAV downloads. Server responses and decode were
checked; operator confirmed successful audio playback. Operator found the played sample understandable but raised pacing/style concerns for a whole episode. Engine attribution and full-cue coverage are unspecified; detailed ratings remain pending.
No machine audio settings were changed. Blank listener scores stay blank until
an actual verdict; put annotations in a fresh receipt, preserving sealed runs.

## Bounded A/B protocol

Freeze `samples/dialogue20.srt` and its hash. Use exactly the same words and
windows for Piper and Kokoro; Fish is a later arm only when one card is safely
available. Assign alternate cues manually to two stock voices for speaker testing;
keep the single-voice Piper control and clearly label that difference. For Fish,
use only authored/permissioned references and log their hashes, text and settings.

Pin code commit, wheel versions, model revision/hash, seed when supported, speed,
voice mapping and device. No concurrency/batching initially. Record cold startup
and first complete WAV latency separately; nonstreaming HTTP latency is not
first-audio streaming latency. Run three complete 20-cue warmups and ten complete
measured repetitions per arm. Alternate arm order between blocks to reduce load
bias; preserve raw per-cue data and report median/p95 latency, RTF spread,
failure/retry count (no automatic retries), CPU seconds, sampled peak RSS,
GPU total/used memory and utilization before/during/after. Label sampling peaks
as observed, not guaranteed maxima. Time normalization and mixing separately.
Use total utterance duration as RTF denominator, not the silent timeline.

Record every overrun/next-start overlap, not just those above 250 ms; retain
untrimmed WAVs. Detect stem and mixed clipping, silence and unexpected truncation.
Blind listening: shuffle engine labels and score intelligibility, pronunciation
(including Ren), naturalness, urgency, question intonation and speaker consistency
1–5; note wrong/missing words and whether both assigned voices remain distinct.
Listening is a human verdict; this session has no listening scores.

Stop an arm after two synthesis failures or one OOM/runtime reset. Allow at most
one isolated remediation and 15 minutes for a tiny Fish setup/smoke; preserve
exceptions. Before any Fish allocation enumerate actual XPU properties and
correlate device selection with PCI BDF; iGPU visibility/order may differ by
runtime filters. Never evict existing models or silently fall back to another device.

## Subtitle acquisition routes

Prefer an operator-exported, authorized caption file or platform-supported
accessible caption track: accurate cue timing and no OCR delay. Use established
subtitle tooling (for example pysubs2) for richer format coverage before expanding
the narrow parser. No service-specific download permission is assumed.

Second option: operator-supplied screenshots of visibly rendered captions with
known media timestamps, then maintained OCR such as Tesseract. Measure text
accuracy, missed/duplicate transitions and observation delay on synthetic frames
first. Sampling at 2 fps alone can delay discovery by up to 500 ms; OCR processing
adds latency. Neither screenshot time nor subtitle display time establishes the
true dialogue boundary. Browser capture rights/platform permissions remain a
source-specific prerequisite. No cookies, stream interception or DRM bypass.
Live pause/seek reconciliation waits until the offline chain passes listening.

## Three next work items

1. **Listen and score (low complexity; about 15 min).** Use the complete
   player URL, listen to all 20 cues, and copy the scoring sheet to a fresh receipt.
   Accept only with intelligibility/pronunciation, acting and speaker-consistency
   judgments. CPU bounding is completed; no longer a prerequisite to rerun.
2. **Phrasing/pause probe (low/medium complexity; about 20 min).** Mark four
   awkward utterances or gaps, then compare identical text and placements with
   one stock voice or rate change at a time. Accept only with intelligibility,
   natural phrasing and listening-comfort evidence plus measured duration/overrun.
   Speeding up may enlarge gaps; choose the lever from the marked defect, not
   generation speed. Preserve baseline WAVs; no truncation or silent text edits.
3. **One-card Fish XPU feasibility (medium/high risk; 15-min smoke once capacity exists).**
   First recheck workload pressure and device mapping; do not free resources by
   changing existing services. One line, compile disabled initially, no casting
   pipeline. Accept only an actual correctly decoded speech WAV with device,
   latency and memory evidence. Then schedule the 20-cue A/B. Current verdict:
   NO-GO for loading Fish alongside the occupied cards.

GO for listening judgments and then one measured timing lever. NO-GO for
live streaming, character-aware dubbing claims or soundtrack separation yet.
