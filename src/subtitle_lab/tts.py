"""Speech backends are interchangeable. No model weights bundled.

Tone is a synchronization test, NOT speech. Piper HTTP is an optional real voice.
WAV-dir permits independently generated speech clips from Fish/other models.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from array import array
from pathlib import Path
import json
import math
import urllib.request
import wave

from .subtitles import Cue

SAMPLE_RATE = 24000


class Engine(ABC):
    @abstractmethod
    def synthesize(self, cue: Cue, destination: Path) -> None:
        """Write a WAV file for this cue; fail on error."""


class ToneEngine(Engine):
    """Audible proof of timeline placement; deliberately not intelligible speech."""
    def synthesize(self, cue: Cue, destination: Path) -> None:
        duration_ms = max(280, min(4000, len(cue.text.split()) * 185))
        count = int(SAMPLE_RATE * duration_ms / 1000)
        freq = 430 + (sum(ord(ch) for ch in (cue.speaker or cue.text)) % 6) * 70
        samples = array("h")
        for i in range(count):
            t = i / SAMPLE_RATE
            envelope = min(1.0, t / .025, (duration_ms / 1000 - t) / .025)
            samples.append(int(6000 * max(0., envelope) * math.sin(2 * math.pi * freq * t)))
        with wave.open(str(destination), "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(SAMPLE_RATE)
            wav.writeframes(samples.tobytes())


class PiperHttpEngine(Engine):
    """Piper v1 HTTP endpoint, defaults to localhost:5000/synthesize."""
    def __init__(self, endpoint: str, speaker_id: int | None = None):
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("Piper endpoint must be http(s) URL")
        self.endpoint = endpoint
        self.speaker_id = speaker_id

    def synthesize(self, cue: Cue, destination: Path) -> None:
        payload: dict = {"text": cue.text}
        if self.speaker_id is not None:
            payload["speaker_id"] = self.speaker_id
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read(35 * 1024 * 1024)  # hard cap for a single utterance
        if not data.startswith(b"RIFF"):
            raise RuntimeError("Piper endpoint did not return a WAV file")
        destination.write_bytes(data)


class WavDirectoryEngine(Engine):
    """Import stems produced by an external model, one named 0001.wav per cue."""
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        if not self.directory.is_dir():
            raise FileNotFoundError(f"Missing stem directory: {self.directory}")

    def synthesize(self, cue: Cue, destination: Path) -> None:
        stem = self.directory / f"{cue.index:04d}.wav"
        if not stem.is_file():
            raise FileNotFoundError(f"Missing speech stem for cue {cue.index}: {stem}")
        destination.write_bytes(stem.read_bytes())
