"""WAV validation, sample-rate conversion and timeline mixing."""
from __future__ import annotations

from array import array
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave

from .tts import SAMPLE_RATE


def wav_frames(path: Path) -> tuple[int, int, int, bytes]:
    with wave.open(str(path), "rb") as reader:
        rate = reader.getframerate()
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        # getnframes is a metadata field; always read actual frames.
        frames = reader.readframes(reader.getnframes())
    return rate, channels, sample_width, frames


def load_pcm16_mono(path: Path, sample_rate: int = SAMPLE_RATE) -> array:
    """Use ffmpeg only when conversion is needed; don't silently degrade audio."""
    rate, channels, width, raw = wav_frames(path)
    if rate != sample_rate or channels != 1 or width != 2:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(
                f"{path.name} is {rate} Hz/{channels} channel(s)/{width * 8}bit. "
                f"Install ffmpeg to normalize to {sample_rate} Hz/mono/PCM16."
            )
        with tempfile.TemporaryDirectory(prefix="subtitle-normalize-") as tmp:
            fixed = Path(tmp) / "normalized.wav"
            call = subprocess.run([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", str(path), "-ar", str(sample_rate), "-ac", "1", "-c:a", "pcm_s16le", str(fixed),
            ], capture_output=True, text=True, timeout=90)
            if call.returncode:
                raise RuntimeError(f"ffmpeg WAV normalization failed: {call.stderr[-500:]}")
            rate, channels, width, raw = wav_frames(fixed)
    if (rate, channels, width) != (sample_rate, 1, 2):
        raise RuntimeError(f"Unexpected output format from WAV normalizer: {path}")
    pcm = array("h")
    pcm.frombytes(raw)
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm


def duration_ms(path: Path) -> int:
    rate, channels, width, raw = wav_frames(path)
    return round(1000 * (len(raw) // (channels * width)) / rate)


def mix_to_wav(placed: list[tuple[int, array]], out_path: Path, end_ms: int,
               sample_rate: int = SAMPLE_RATE) -> dict:
    """Sum overlapping voices on one timeline. Clip detection is recorded, not hidden."""
    if end_ms > 2 * 60 * 60 * 1000:
        raise ValueError("Prototype render limit: 2 hours; implement streaming mix for longer media")
    count = max(1, (end_ms * sample_rate + 999) // 1000)
    accumulation = array("f", [0.0]) * count
    for start_ms, pcm in placed:
        offset = round(start_ms * sample_rate / 1000)
        for i, sample in enumerate(pcm):
            pos = offset + i
            if pos < count:
                accumulation[pos] += sample * 0.72  # conservative headroom per stem
    clipped = sum(1 for n in accumulation if abs(n) > 32767)
    peak = max(abs(n) for n in accumulation)
    output = array("h", (int(max(-32768, min(32767, round(x)))) for x in accumulation))
    if sys.byteorder != "little":
        output.byteswap()
    with wave.open(str(out_path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate)
        wav.writeframes(output.tobytes())
    return {"sample_rate": sample_rate, "peak_preclip_pcm16": round(peak, 1),
            "clipped_samples": clipped, "timeline_duration_ms": round(count * 1000 / sample_rate)}
