"""End-to-end local subtitle -> individual clips -> synchronized WAV + receipt."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import time

from .audio import duration_ms, load_pcm16_mono, mix_to_wav
from .subtitles import load_cues, summary
from .tts import Engine, SAMPLE_RATE


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def render(source: Path, destination: Path, engine: Engine, engine_name: str) -> dict:
    """Create a new, non-overwriting run; retain outputs and an auditable manifest."""
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    cues = sorted(load_cues(source), key=lambda cue: (cue.start_ms, cue.index))
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing run: {destination}")
    destination.mkdir(parents=True)
    stems_dir = destination / "stems"
    stems_dir.mkdir()
    (destination / "cues.json").write_text(
        json.dumps([cue.to_dict() for cue in cues], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (destination / "transcript.txt").write_text(
        "\n".join(f"[{cue.start_ms/1000:08.3f} -> {cue.end_ms/1000:08.3f}] "
                  f"{cue.speaker + ': ' if cue.speaker else ''}{cue.text}" for cue in cues) + "\n",
        encoding="utf-8"
    )
    placements = []
    records = []
    utterance_end = 0
    for ordinal, cue in enumerate(cues):
        stem = stems_dir / f"{cue.index:04d}.wav"
        started = time.perf_counter()
        engine.synthesize(cue, stem)
        elapsed = round((time.perf_counter() - started) * 1000)
        pcm = load_pcm16_mono(stem)
        spoken_ms = round(len(pcm) * 1000 / SAMPLE_RATE)
        utterance_end = max(utterance_end, cue.start_ms + spoken_ms)
        placements.append((cue.start_ms, pcm))
        next_start = cues[ordinal + 1].start_ms if ordinal + 1 < len(cues) else None
        records.append({
            **asdict(cue),
            "stem": f"stems/{stem.name}", "stem_sha256": file_sha256(stem),
            "speech_duration_ms": spoken_ms,
            "generation_wall_ms": elapsed,
            "cue_overrun_ms": max(0, cue.start_ms + spoken_ms - cue.end_ms),
            "speech_overlap_next_ms": (max(0, cue.start_ms + spoken_ms - next_start)
                                      if next_start is not None else 0),
            "speech_slack_ms": max(0, cue.end_ms - cue.start_ms - spoken_ms),
        })
    audio_path = destination / "dub.wav"
    mix = mix_to_wav(placements, audio_path,
                     end_ms=max(max(c.end_ms for c in cues), utterance_end) + 200)
    warnings = []
    overrun_count = sum(r["cue_overrun_ms"] > 250 for r in records)
    if overrun_count:
        warnings.append(f"{overrun_count} cues exceed source subtitle window by >250ms")
    overlap_count = sum(r["speech_overlap_next_ms"] > 250 for r in records)
    if overlap_count:
        warnings.append(f"{overlap_count} speech clips overlap start of next subtitle by >250ms")
    if mix["clipped_samples"]:
        warnings.append(f"Mixed PCM clipped at {mix['clipped_samples']} samples")
    result = {
        "schema_version": "subtitle-lab-render-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source), "source_sha256": file_sha256(source),
        "engine": engine_name, "sample_rate": SAMPLE_RATE,
        "input_summary": summary(cues),
        "audio": {"file": "dub.wav", "sha256": file_sha256(audio_path), **mix},
        "metrics": {
            "cue_count": len(records),
            "cue_overruns_gt_250ms": overrun_count,
            "speech_overlap_next_gt_250ms": overlap_count,
            "aggregate_generation_ms": sum(r["generation_wall_ms"] for r in records),
            "source_length_ms": max(c.end_ms for c in cues),
        },
        "warnings": warnings,
        "cues": records,
    }
    (destination / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# Subtitle Lab — render receipt", "",
        f"- Source: `{source.name}` (`{result['source_sha256'][:12]}…`)",
        f"- Engine: `{engine_name}` (tone != speech)",
        f"- Cues: {len(records)}",
        f"- Source duration: {result['metrics']['source_length_ms']/1000:.2f}s",
        f"- Mixed track duration: {mix['timeline_duration_ms']/1000:.2f}s",
        f"- Inference wall time (sum): {result['metrics']['aggregate_generation_ms']/1000:.3f}s",
        f"- Overrun >250ms: {overrun_count}",
        f"- Next-start overlap >250ms: {overlap_count}",
        f"- Clipped PCM samples: {mix['clipped_samples']}", "",
        "## Known limits", "",
        "- Start timestamps are used as-is; there is NO forced alignment or dialogue shortening.",
        "- Overlapping speech is simply summed; music/dialogue separation is NOT performed.",
        "- TTS character assignment is manual/unimplemented; cues without names use one voice.",
        "- 'tone' generates nonverbal diagnostics, not an intelligible dub.",
        "- Current mixer is mono PCM16; production-quality stem mixing is a future gate.",
        "", "## Warnings", "",
    ]
    report += [f"- {warning}" for warning in warnings] if warnings else ["- None within the measured criteria."]
    (destination / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return result


def validate(path: Path) -> dict:
    path = path.resolve()
    if path.is_dir():
        path = path / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent
    if manifest["schema_version"] != "subtitle-lab-render-v1":
        raise ValueError("Unknown manifest schema")
    expected = [(manifest["audio"]["file"], manifest["audio"]["sha256"])]
    for record in manifest["cues"]:
        expected.append((record["stem"], record["stem_sha256"]))
    for file, digest in expected:
        target = (root / file).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"Unsafe receipt file path: {file}")
        if not target.is_file() or file_sha256(target) != digest:
            raise RuntimeError(f"Missing or changed render artifact: {file}")
    return {
        "status": "PASS", "validated_files": len(expected), "source_sha256": manifest["source_sha256"],
        "mixed_wav_duration_ms": duration_ms(root / manifest["audio"]["file"]),
        "warnings": manifest["warnings"],
    }
