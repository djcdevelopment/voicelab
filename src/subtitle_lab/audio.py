"""WAV validation, sample-rate conversion and timeline mixing."""
from __future__ import annotations

from array import array
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave
import math

from .tts import SAMPLE_RATE


def wav_frames(path: Path) -> tuple[int, int, int, bytes]:
    with wave.open(str(path), "rb") as reader:
        rate = reader.getframerate()
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        # getnframes is a metadata field; always read actual frames.
        frames = reader.readframes(reader.getnframes())
        if len(frames) != reader.getnframes() * channels * sample_width:
            raise ValueError(f"Truncated WAV data: {path.name}")
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


def write_pcm16(path: Path, pcm: array, sample_rate: int = SAMPLE_RATE) -> None:
    raw = array('h', pcm)
    if sys.byteorder != 'little':
        raw.byteswap()
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate)
        wav.writeframes(raw.tobytes())


def tempo_pcm(pcm: array, destination: Path, factor: float) -> array:
    """Explicit pitch-preserving FFmpeg tempo change; preserve the complete utterance."""
    if not math.isfinite(factor) or not 1 <= factor <= 1.5:
        raise ValueError('Fit tempo factor must be between 1 and 1.5')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg is required for explicit tempo fitting')
    temporary = destination.with_suffix('.input.wav')
    write_pcm16(temporary, pcm)
    try:
        result = subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-n',
            '-i',str(temporary),'-af',f'atempo={factor:.9f}',
            '-ar',str(SAMPLE_RATE),'-ac','1','-c:a','pcm_s16le',str(destination)],
            capture_output=True,text=True,timeout=90)
        if result.returncode:
            raise RuntimeError(f'FFmpeg tempo failed: {result.stderr[-1000:]}')
        return load_pcm16_mono(destination)
    finally:
        temporary.unlink(missing_ok=True)


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
        if start_ms < 0:
            raise ValueError('Negative cue start cannot be mixed')
        offset = round(start_ms * sample_rate / 1000)
        if offset + len(pcm) > count:
            raise ValueError('Mix end would truncate an utterance')
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
