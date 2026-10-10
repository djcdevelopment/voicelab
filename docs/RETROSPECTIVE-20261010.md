# Subtitle Lab retrospective — 2026-10-10

The session established a working local subtitle-to-speech bench and synthetic
synchronized playback. It did not establish a convincing full-episode dub.
The operator found speech understandable, then preferred particular improved
excerpts while retaining concerns about pacing, style and female syllable emphasis.

## What worked

The starter architecture was sufficient. Its subtitle parser, Engine contract and
WAV-directory adapter enabled real Piper and Kokoro trials without a serving
platform. A real WebVTT metadata defect received a small regression repair.
The suite grew from 12 to 35 tests while preserving the standard-library smoke.

Three warmups plus ten measured 20-cue sets produced repeatable CPU evidence.
Explicit ONNX threading mattered: taskset alone did not constrain Piper workers.
The failed resource attempt remained recorded alongside the corrected run.

Keeping raw stems made overflow measurable and capped tempo experiments reviewable.
Explicit media-clock mapping, source binding, Range-capable HTTP serving and
decoded AAC comparisons proved authored offline playback through pause and seeks.
Caption auditing correctly rejected full-film subtitles paired with a trailer.

Human feedback selected Bella for fitted four-cue dialogue and Heart for normal
12-cue conversation. Hash-bound selection records removed ambiguity about which
bottom player was preferred. These judgments are useful controls, not a universal
engine or voice ranking.

## What cost unnecessary effort

Incomplete playback links and WAV opening behavior made listening harder than it
needed to be. Complete clickable localhost links, MP3 listening copies and a
working player reduced that burden. Future reviews should lead with those links.

The basic file server could serve bytes but failed browser seeking. Using maintained
Werkzeug conditional responses resolved the observed issue. Media delivery needed
an actual seek check, not only an HTTP success response.

Successive append-only feedback sections in editable docs left stale statements
beside newer verdicts. Immutable receipts should preserve chronology; current docs
should state the latest decision once. This closeout reconciles those sections.

Additional variants could not resolve an unspecified pronunciation defect or prove
episode comfort. A specific word/cue is the next useful voice input. Repeated
full-film mirror attempts also did not produce matching media; the mismatch and
access failures are sufficient blockers, not an invitation to expand acquisition.

## Next slice and verdict

GO for one targeted CPU phrasing probe after a problematic cue is identified, or
one authorized matching video/caption trial after local files become available.
Require listener-confirmed improvement and measured residual timing defects for
the first; source/clock audit, browser checks and human playback for the second.

NO-GO for whole-episode quality claims, live integration or Fish allocation on
occupied cards. Automatic casting and soundtrack recovery remain separate gates.
The broader research objective remains unfinished; this documentation closeout
does not change that verdict.

All existing work was already committed on master. This closeout adds documentation,
a decision record and a fresh local receipt. There are no other local branches to
merge and no remote configured. Push authorization was given, but an actual
destination is still required; no remote was guessed or created.
