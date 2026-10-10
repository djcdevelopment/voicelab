# Subtitle Lab frontier plan — 2026-10-10

G0–G3 have running CPU evidence; intelligibility is provisionally positive,
with operator pacing/style concerns. Manual casting, capped tempo fitting,
local text-track extraction and offline synchronized playback now have synthetic
technical evidence. Listener quality and real-source performance remain open.
Fish XPU remains a plan, with occupied cards and no host inference claim.
Machine details remain in ignored receipts, including `bench-build-20261010-01`.

The extracted checkout is the session workspace; the requested `/work/subtitle`
was empty. Work stayed in the existing checkout. No existing service was changed.
The original smoke passed 12 tests; the latest suite contains 35 tests; optional integrations skip on a bare host. The original parser repair brought the suite to 13. SRT, VTT and ASS
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
| Kokoro-82M | Ran on host CPU with two stock voices; acting/listening unassessed | Alternate Heart/Michael cues, speed 1.0; no exact duration or inferred identity | Two-core mean generation RTF 0.2521; observed bench RSS 1928.6 MiB. Isolated Torch/Misaki/espeakng-loader; six >250 ms overruns per set | Apache-2.0 weights; native CPU engine and wav-dir available; Piper fallback |
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

1. **Pacing/style listening probe (low complexity, 15–20 min).** Use the first-four-cue
   player at http://127.0.0.1:18576/short-review/index.html . Original Kokoro,
   speed 0.95 and capped tempo 1.15 use identical words and placements. The slower
   full set has seven >250 ms overruns, original six, fitted five; that is timing
   evidence, not a quality winner. Accept only after a listener identifies the
   awkward cue/gap and scores phrasing/comfort. Choose one voice or performance
   lever from that defect; preserve words and original audio.
2. **Matching permissioned video trial (medium complexity, 20–30 min once available).**
   A real-caption slice now downloaded CC BY Sintel captions: 26 cues agree with
   pysubs2 and synthesize on both CPU engines. Audio comparison:
   http://127.0.0.1:18579/review/index.html . The available W3C video is a trailer;
   `audit-captions` rejects the full-film captions against it. Full-film routes
   returned 403; the source mismatch remains unresolved.
   Extract one authorized local text track, audit timestamps/line completeness,
   synthesize and compose. Synthetic 20-cue extraction currently has zero missing,
   duplicate, text or timing errors; both playback seeks pass. Accept only with
   real-source clock mapping and human playback evidence, without cutting speech.
   Explicit `--clock video` now maps a nonzero first-frame PTS to playback zero;
   mismatched source/clock or pre-video captions fail. The synthetic 5-second-offset
   trial passes all 20 cue comparisons and browser pause/seek/caption checks. Soundtrack separation needs
   its own later experiment; an authored background bed does not solve it.
3. **One-card Fish XPU smoke (medium/high risk, 15-min bound when capacity exists).**
   Recheck actual device mapping and workload pressure. One permissioned line,
   isolated env, compile disabled initially, no unrelated workload changes.
   Accept only decoded English speech with actual device/memory/latency records.
   Then run the fixed 20-cue, 3-warmup/10-measurement comparison. Current NO-GO:
   occupied cards; upstream XPU support does not establish B70 compatibility.

GO for short listening probes and authorized offline source trials. NO-GO for
whole-episode quality claims, live streaming or Fish loading on occupied cards.

## Latest operator listening feedback

Operator: “those are getting better.” This is positive perceived improvement, with
sample/engine/variant attribution still unspecified. It does not establish a model
winner or whole-episode comfort. Baselines remain unchanged. Clarify the preferred
comparison/variant before choosing a single phrasing/pause lever for the next pass.
New feedback receipt: `output/RECEIPTS/listening-feedback-20261010-01/`.

## Attributed listening verdict and female voice probe

Operator prefers the bottom option of each comparison: capped 1.15 Kokoro timing
adjustment, and Kokoro Heart on the Piper/Kokoro conversation. Female first-syllable
emphasis remains a perceived defect. These are relative sample judgments, not a
whole-episode or general engine-quality verdict.

A matched Heart→Bella stock-voice probe keeps words/windows, speed, seed and timing
policy fixed. All ten male source stems match exactly. Bella's conversation has a
625 ms next-cue overlap at cue 3, so Heart remains preferred pending a style verdict.
No code changed or redundant tests rerun; new immutable receipt:
`output/RECEIPTS/female-voice-probe-20261010-01/`.

- Synthetic: http://127.0.0.1:18580/synthetic-review/index.html
- Conversation: http://127.0.0.1:18580/conversation-review/index.html

The preferred Heart is first on the synthetic page and second on the conversation
page. Bella is a probe, with no claimed improvement until actual listening.

## Latest page-relative preferences

Operator again preferred the bottom audio on both new pages. Player order proves:

- **Four-cue dialogue:** Bella with capped 1.15 timing, male Michael unchanged.
- **Twelve-cue conversation:** Heart at normal speed.

Selected original renders/audio hashes are recorded in the new immutable receipt
`output/RECEIPTS/listening-preference-20261010-01/`. Keep these as separate preferred
controls. The samples differ in corpus and timing policy, so this does not establish
an overall voice ranking. The first-syllable criticism was not explicitly revisited;
pronunciation details, speaker consistency and episode-length comfort remain open.
Both original full WAVs and earlier comparison pages remain intact.
