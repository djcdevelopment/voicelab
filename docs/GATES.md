# Experiment gates and stop/go criteria

Gate status in this **starter archive** is *implementation status only*. No benchmarks have been run on the user's Arc workstation.

| Gate | Purpose | Objective acceptance evidence | Starter status |
|---|---|---|---|
| G0 | Survey repo and hardware without disruption | Read-only doctor receipt, XPU enumeration (discrete vs integrated), tools/versions, workloads and available VRAM | Command implemented; not run on user machine |
| G1 | Reproducible subtitle clock | SRT/VTT/ASS fixtures, malformed/overlap cases, deterministic cue JSON and parser tests | Implemented, synthetic fixtures |
| G2 | Local timed audio | Test tone → stems/mixed WAV, checksum validation, timing-overrun report | Implemented |
| G3 | Intelligible local English voice | Piper or preexisting TTS produces English WAV, at least 20 representative lines, RTF and duration error recorded | Adapter present; requires user-host TTS |
| G4 | Arc expressive TTS feasibility | Evaluate 1+ credible voices on actual B70; XPU-only results, repeatable environment, performance and fidelity sample set | Not attempted |
| G5 | Character-aware dub slice | 2+ distinct consistent voices and real duration-fitting experiment with listener assessment | Not attempted |
| G6 | Subtitle acquisition adapter | One authorized source proven end-to-end; measure missing/duplicate/error rates | Not attempted |
| G7 | Scene-synchronized playback | Live or offline sync with pause/seek correctness; soundtrack options measured | Not attempted |

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
