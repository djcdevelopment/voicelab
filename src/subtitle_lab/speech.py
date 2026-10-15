"""Untimed text speech using the same engines as subtitle rendering.

Paragraph gaps are inserted silence, not subtitle deadlines or speech trimming.
Only engine construction imports optional packages; tone remains stdlib-only.
"""
from __future__ import annotations

from array import array
from datetime import datetime, timezone
from pathlib import Path
import json
import platform
import re
import sys
import time

from .audio import load_pcm16_mono, write_pcm16, wav_frames
from .pipeline import file_sha256, speech_activity
from .subtitles import Cue
from .tts import SAMPLE_RATE, ToneEngine
from .voices import VoicePlan, VoiceSettings


def paragraphs(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Paste some text before generating speech')
    if len(text) > 5000:
        raise ValueError('Text is limited to 5,000 characters per request')
    if '\x00' in text:
        raise ValueError('Text must not contain NUL characters')
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    return [re.sub(r'\s*\n\s*', ' ', p).strip()
            for p in re.split(r'\n[ \t]*\n+', normalized) if p.strip()]


def settings_for(engine: str, voice: str | None, speed: float, paragraph_pause_ms: int) -> dict:
    if engine not in ('kokoro', 'piper-local', 'tone'):
        raise ValueError('Text speech requires kokoro, piper-local, or diagnostic tone')
    VoicePlan(VoiceSettings(speed=speed))
    if type(paragraph_pause_ms) is not int or not 0 <= paragraph_pause_ms <= 1500:
        raise ValueError('Paragraph pause must be an integer from 0 to 1500 ms')
    if engine == 'kokoro':
        voice = voice or 'af_heart'
        if not re.fullmatch(r'a[fm]_[a-z0-9_]+', voice):
            raise ValueError('Choose an installed American English Kokoro voice')
    elif voice is not None:
        raise ValueError('Named voices are supported only by Kokoro; Piper uses its model')
    return dict(engine=engine, voice=voice, speed=speed, paragraph_pause_ms=paragraph_pause_ms)


def speak(text: str, destination: Path, *, engine_name='kokoro', voice=None,
          speed=1.0, paragraph_pause_ms=250, threads=2,
          model=Path('models/piper/en_US-lessac-medium.onnx'),
          model_dir=Path('models/kokoro')) -> dict:
    spoken = paragraphs(text)
    settings = settings_for(engine_name, voice, speed, paragraph_pause_ms)
    if type(threads) is not int or not 1 <= threads <= 8:
        raise ValueError('CPU threads must be an integer from 1 to 8')
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    began = time.perf_counter()
    (destination / 'source.txt').write_text(text, encoding='utf-8', newline='')
    (destination / 'request.json').write_text(json.dumps(settings, indent=2) + '\n')
    try:
        loading = time.perf_counter()
        if engine_name == 'tone':
            engine = ToneEngine()
        else:
            from .local_tts import KokoroEngine, PiperLocalEngine
            plan = VoicePlan(VoiceSettings(voice=settings['voice'], speed=speed))
            engine = (KokoroEngine(model_dir, plan, threads) if engine_name == 'kokoro'
                      else PiperLocalEngine(model, plan, threads))
        startup_ms = round((time.perf_counter() - loading) * 1000)
        stems = destination / 'stems'
        stems.mkdir()
        combined = array('h')
        records = []
        silence = array('h', [0]) * (paragraph_pause_ms * SAMPLE_RATE // 1000)
        for index, text_part in enumerate(spoken, 1):
            stem = stems / f'{index:04d}.wav'
            started = time.perf_counter()
            # The engine interface needs a Cue; no artificial time window is
            # recorded or used to place, speed up, or truncate plain speech.
            engine.synthesize(Cue(index, 0, 0, text_part), stem)
            generation_ms = round((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            pcm = load_pcm16_mono(stem)
            if not pcm:
                raise RuntimeError(f'Empty speech for paragraph {index}')
            normalization_ms = round((time.perf_counter() - started) * 1000)
            if index > 1:
                combined.extend(silence)
            start_sample = len(combined)
            combined.extend(pcm)
            records.append(dict(index=index, text=text_part, stem=f'stems/{stem.name}',
                                start_sample=start_sample, samples=len(pcm),
                                generation_ms=generation_ms, normalization_ms=normalization_ms,
                                engine_details=engine.cue_details(), **speech_activity(pcm)))
        write_pcm16(destination / 'speech.wav', combined)
        provenance = engine.describe()
        provenance['model_sha256'] = {
            name: file_sha256(Path(name)) for name in provenance.get('model_files', [])}
        audio_ms = len(combined) * 1000 / SAMPLE_RATE
        speech_ms = sum(p['samples'] for p in records) * 1000 / SAMPLE_RATE
        generation_ms = sum(p['generation_ms'] for p in records)
        result = dict(schema_version='subtitle-lab-speech-v1', status='completed',
                      generated_at_utc=datetime.now(timezone.utc).isoformat(),
                      settings=settings, paragraphs=records, sample_rate=SAMPLE_RATE,
                      audio='speech.wav', source_snapshot='source.txt',
                      source_sha256=file_sha256(destination / 'source.txt'),
                      engine_provenance=provenance,
                      environment=dict(python=sys.version, platform=platform.platform()),
                      command=sys.argv, timing_policy=dict(mode='paragraph-gap', truncate=False),
                      metrics=dict(startup_ms=startup_ms, generation_ms=generation_ms,
                                   normalization_ms=sum(p['normalization_ms'] for p in records),
                                   total_ms=round((time.perf_counter() - began) * 1000),
                                   audio_ms=audio_ms, speech_ms=speech_ms,
                                   inserted_silence_ms=paragraph_pause_ms * (len(records) - 1),
                                   generation_rtf=generation_ms / speech_ms,
                                   **speech_activity(combined)))
        result['artifacts'] = {str(p.relative_to(destination)): file_sha256(p)
                               for p in sorted(destination.rglob('*')) if p.is_file()}
        (destination / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        return result
    except BaseException as exc:
        (destination / 'failure.json').write_text(json.dumps(dict(
            status='failed', exception=type(exc).__name__, message=str(exc),
            elapsed_ms=round((time.perf_counter() - began) * 1000)), indent=2) + '\n')
        raise


def validate_speech(root: Path, manifest: dict) -> dict:
    """Check source identity, every artifact, and exact sample placement."""
    artifacts = manifest['artifacts']
    records = manifest['paragraphs']
    required = {'source.txt', 'request.json', 'speech.wav'} | {r['stem'] for r in records}
    if not records or not required <= artifacts.keys():
        raise ValueError('Speech manifest omits required artifacts')
    for name, digest in artifacts.items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError('Unsafe speech artifact path')
        if not target.is_file() or file_sha256(target) != digest:
            raise ValueError(f'Missing or changed speech artifact: {name}')
    source = (root / 'source.txt').read_text(encoding='utf-8')
    if paragraphs(source) != [p['text'] for p in records]:
        raise ValueError('Spoken paragraphs differ from source')
    if file_sha256(root / 'source.txt') != manifest['source_sha256']:
        raise ValueError('Source identity differs')
    settings = manifest['settings']
    settings_for(**settings)
    if settings != json.loads((root / 'request.json').read_text()):
        raise ValueError('Manifest settings differ from request')
    if manifest['timing_policy'] != {'mode': 'paragraph-gap', 'truncate': False}:
        raise ValueError('Unexpected speech timing policy')
    rate, channels, width, raw = wav_frames(root / 'speech.wav')
    if (rate, channels, width) != (SAMPLE_RATE, 1, 2):
        raise ValueError('Unexpected speech WAV format')
    gap = settings['paragraph_pause_ms'] * SAMPLE_RATE // 1000
    expected = 0
    for index, record in enumerate(records):
        if index:
            if any(raw[expected * 2:(expected + gap) * 2]):
                raise ValueError('Paragraph gap is not silence')
            expected += gap
        if record['start_sample'] != expected or record['samples'] <= 0:
            raise ValueError('Invalid paragraph sample placement')
        # Duration conversion is checked without requiring optional FFmpeg.
        sr, ch, sw, stem_raw = wav_frames(root / record['stem'])
        if abs(len(stem_raw) / (ch * sw * sr) - record['samples'] / SAMPLE_RATE) > .002:
            raise ValueError('Paragraph duration differs from original speech')
        expected += record['samples']
    if expected * 2 != len(raw):
        raise ValueError('Speech output is truncated or has unexpected padding')
    if abs(manifest['metrics']['audio_ms'] - expected * 1000 / SAMPLE_RATE) > .001:
        raise ValueError('Speech duration metric differs from audio')
    return dict(status='PASS', validated_files=len(artifacts),
                source_sha256=manifest['source_sha256'], speech_duration_ms=expected * 1000 / SAMPLE_RATE)
