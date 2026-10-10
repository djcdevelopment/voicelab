# ADR 0001 — CPU speech baseline and evidence gates

Date: 2026-10-10. Status: accepted for the current experiment bench.

## Context

The initial question was whether timed English subtitles can yield usable local
speech without disturbing existing inference workloads. Piper and Kokoro ran on
CPU; Fish has upstream XPU guidance but no safe available card in this session.
Fast synthesis and passing clock tests did not establish episode listening quality.

## Decision

Keep the compact file → cue → engine → original WAV → measured fit → mix path.
Use bounded CPU Piper as the functional baseline and local Kokoro stock voices
for targeted performance probes. Accept new unverified engines through cue-numbered
WAV imports before adding an API adapter. Preserve the dependency-free smoke path.

Retain original stems and source timing. Tempo fitting is explicit, capped and
reported; residual overflow is a result, never silently hidden by truncation.
Bind extracted subtitles to source identity and clock mode, and audit caption
bounds before a real-media render. Matching bounds alone do not prove matching cuts.

Keep Bella fitted synthetic dialogue and Heart normal-speed conversation as
separate preferred listening controls. Do not change a global default from these
unblinded, differently timed excerpts. Require a specific defect and a human
verdict before another performance change.

Fish requires fresh runtime/device mapping and safe capacity without evicting
workloads. Source separation, inferred casting, OCR and live playback remain
separate later gates. No cloud fallback or new orchestration layer is introduced.

## Consequences and evidence

CPU synthesis and synthetic offline playback are reproducible now. Convincing
episode performance, matching real-media playback and Fish compatibility remain
unproven. Model environments, media and machine-specific receipts stay local.
See [completion audit](../COMPLETION-AUDIT.md), [handoff](../HANDOFF.md) and
[retrospective](../RETROSPECTIVE-20261010.md). This decision can be revisited after
the next acceptance gate produces new evidence.
