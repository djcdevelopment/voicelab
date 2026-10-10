"""Small, dependency-free SRT/VTT/ASS subtitle ingest layer.

This is a time-and-text parser, not a complete subtitle renderer. It intentionally
ignores typography/position/animations, and retains source timestamps.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
import re


@dataclass(frozen=True)
class Cue:
    index: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


STAMP = r"(?:\d{1,2}:)?\d{1,2}:\d{2}[,.]\d{1,3}"
TIMING = re.compile(rf"^\s*(?P<start>{STAMP})\s*-->\s*(?P<end>{STAMP})(?:\s+.*)?$")
VTT_SPEAKER = re.compile(r"<v\s+([^>]+)>", flags=re.IGNORECASE)
ASS_OVERRIDE = re.compile(r"\{\\[^}]*\}")
HTML_TAG = re.compile(r"<[^>]+>")


def timestamp_ms(value: str) -> int:
    """Parse hh:mm:ss.mmm or mm:ss.mmm (also comma decimal)."""
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        hh, mm, secpart = 0, int(parts[0]), parts[1]
    elif len(parts) == 3:
        hh, mm, secpart = int(parts[0]), int(parts[1]), parts[2]
    else:
        raise ValueError(f"Bad subtitle timestamp: {value!r}")
    if "." not in secpart:
        raise ValueError(f"Timestamp missing decimal fraction: {value!r}")
    ss, frac = secpart.split(".", 1)
    if not (ss.isdigit() and frac.isdigit() and 1 <= len(frac) <= 3):
        raise ValueError(f"Bad subtitle timestamp: {value!r}")
    sec = int(ss)
    if not (0 <= mm < 60 and 0 <= sec < 60 and hh >= 0):
        raise ValueError(f"Out-of-range subtitle timestamp: {value!r}")
    return ((hh * 3600 + mm * 60 + sec) * 1000) + int(frac.ljust(3, "0"))


def plain_text(value: str, *, ass: bool = False) -> str:
    if ass:
        value = ASS_OVERRIDE.sub("", value)
        value = value.replace(r"\N", "\n").replace(r"\n", "\n").replace(r"\h", " ")
    value = HTML_TAG.sub("", value)
    value = unescape(value)
    return " ".join(value.split())


def _append(cues: list[Cue], start: int, end: int, text: str, speaker: str | None = None) -> None:
    if end <= start:
        raise ValueError(f"Subtitle cue has nonpositive duration: {start} -> {end}")
    text = text.strip()
    if not text:
        return
    cues.append(Cue(index=len(cues) + 1, start_ms=start, end_ms=end, text=text, speaker=speaker))


def parse_srt_vtt(content: str) -> list[Cue]:
    lines = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues: list[Cue] = []
    i = 0
    while i < len(lines):
        # WebVTT metadata blocks can contain timing-looking examples. They
        # are not dialogue and must never reach speech synthesis.
        if re.match(r"^(?:NOTE(?:[ \t].*)?|STYLE|REGION)$", lines[i].strip()):
            while i < len(lines) and lines[i].strip():
                i += 1
            continue
        match = TIMING.match(lines[i])
        if match is None:
            i += 1
            continue
        start, end = timestamp_ms(match.group("start")), timestamp_ms(match.group("end"))
        i += 1
        subtitle_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            subtitle_lines.append(lines[i]); i += 1
        raw = "\n".join(subtitle_lines)
        speaker_match = VTT_SPEAKER.search(raw)
        speaker = speaker_match.group(1).strip() if speaker_match else None
        _append(cues, start, end, plain_text(raw), speaker)
    return cues


def parse_ass(content: str) -> list[Cue]:
    """Extract ASS dialogue using its [Events] Format columns; no rendering fidelity."""
    fields = ["Layer", "Start", "End", "Style", "Name", "MarginL", "MarginR", "MarginV", "Effect", "Text"]
    cues: list[Cue] = []
    events = False
    for raw in content.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            events = (line.lower() == "[events]")
            continue
        if not events:
            continue
        if line.lower().startswith("format:"):
            fields = [col.strip() for col in line.split(":", 1)[1].split(",")]
            continue
        if not line.lower().startswith("dialogue:"):
            continue
        values = [v.strip() for v in line.split(":", 1)[1].strip().split(",", len(fields) - 1)]
        if len(values) != len(fields):
            raise ValueError("Malformed ASS Dialogue row (does not match Format)")
        data = dict(zip(fields, values))
        for required in ("Start", "End", "Text"):
            if required not in data:
                raise ValueError(f"ASS Format lacks {required}")
        name = data.get("Name", "").strip() or None
        _append(cues, timestamp_ms(data["Start"]), timestamp_ms(data["End"]),
                plain_text(data["Text"], ass=True), name)
    return cues


def load_cues(path: str | Path) -> list[Cue]:
    path = Path(path)
    contents = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in (".srt", ".vtt"):
        cues = parse_srt_vtt(contents)
    elif path.suffix.lower() in (".ass", ".ssa"):
        cues = parse_ass(contents)
    else:
        raise ValueError(f"Unsupported extension {path.suffix!r}; expected .srt .vtt .ass .ssa")
    if not cues:
        raise ValueError("No timed dialogue cues parsed; inspect source format/encoding")
    return cues


def summary(cues: list[Cue]) -> dict:
    ordered = sorted(cues, key=lambda c: (c.start_ms, c.index))
    spans = [c.end_ms - c.start_ms for c in cues]
    return {
        "cue_count": len(cues),
        "duration_ms": max(c.end_ms for c in cues),
        "median_cue_ms": sorted(spans)[len(spans) // 2],
        "overlapping_source_cues": sum(a.end_ms > b.start_ms for a, b in zip(ordered, ordered[1:])),
        "speakers_named": sorted({c.speaker for c in cues if c.speaker}),
        "estimated_text_characters": sum(len(c.text) for c in cues),
    }
