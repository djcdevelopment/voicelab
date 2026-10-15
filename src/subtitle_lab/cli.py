"""`python -m subtitle_lab` CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .doctor import doctor
from .pipeline import render, validate
from .subtitles import load_cues, summary
from .tts import PiperHttpEngine, ToneEngine, WavDirectoryEngine
from .voices import VoicePlan, VoiceSettings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Subtitle Lab local timed-text-to-audio R&D")
    commands = parser.add_subparsers(dest="command", required=True)
    speaker = commands.add_parser('speak', help='Turn plain UTF-8 text into complete speech')
    speaker.add_argument('--text-file', required=True, help='UTF-8 file, or - to read pasted/piped stdin')
    speaker.add_argument('--engine', choices=('kokoro', 'piper-local', 'tone'), default='kokoro')
    speaker.add_argument('--voice')
    speaker.add_argument('--speed', type=float, default=1.0)
    speaker.add_argument('--paragraph-pause-ms', type=int, default=250)
    speaker.add_argument('--threads', type=int, default=2)
    speaker.add_argument('--model', type=Path, default=Path('models/piper/en_US-lessac-medium.onnx'))
    speaker.add_argument('--model-dir', type=Path, default=Path('models/kokoro'))
    speaker.add_argument('--out', type=Path, required=True)
    diag = commands.add_parser("doctor", help="Read-only local Intel/GPU/tool discovery")
    diag.add_argument("--out", type=Path)
    inspect = commands.add_parser("inspect", help="Parse SRT/VTT/ASS and report cue stats")
    inspect.add_argument("source", type=Path)
    inspect.add_argument("--out", type=Path, help="Optional JSON report path")
    renderer = commands.add_parser("render", help="Generate stems, mixed WAV, and receipts")
    renderer.add_argument("source", type=Path)
    renderer.add_argument("--engine", choices=("tone", "piper-http", "piper-local", "kokoro", "wav-dir"), default="tone")
    renderer.add_argument("--out", type=Path, required=True, help="New output directory; never overwritten")
    renderer.add_argument("--piper-url", default="http://127.0.0.1:5000/synthesize")
    renderer.add_argument("--speaker-id", type=int)
    renderer.add_argument("--wav-dir", type=Path, help="Directory containing 0001.wav, 0002.wav, etc.")
    renderer.add_argument("--model", type=Path, help="Existing Piper .onnx model")
    renderer.add_argument("--model-dir", type=Path, default=Path('models/kokoro'))
    renderer.add_argument("--voice", help="Local Kokoro stock voice name")
    renderer.add_argument("--speed", type=float, default=1.0, help="Explicit synthesis rate; 1 is normal")
    renderer.add_argument("--threads", type=int, default=2, help="Bound local speech to this many CPU workers")
    renderer.add_argument("--cast", type=Path, help="Manual voice/speaker/cue assignment JSON")
    renderer.add_argument("--fit-max-speedup", type=float, help="Opt-in FFmpeg tempo fitting, capped from 1 to 1.5")
    checker = commands.add_parser("validate", help="Verify SHA256 of rendered WAV and stems")
    checker.add_argument("run", type=Path)
    probe = commands.add_parser('probe-media',help='Read-only stream inventory of authorized local media')
    probe.add_argument('source',type=Path)
    audit = commands.add_parser('audit-captions',help='Read-only caption/video window check before synthesis; not word alignment')
    audit.add_argument('source',type=Path)
    audit.add_argument('captions',type=Path)
    audit.add_argument('--clock',choices=('source','video'),default='source',help='Clock already used by the supplied captions')
    audit.add_argument('--out',type=Path)
    extract = commands.add_parser('extract',help='Extract an authorized local text caption track with FFmpeg')
    extract.add_argument('source',type=Path)
    extract.add_argument('--subtitle-index',type=int,default=0)
    extract.add_argument('--clock',choices=('source','video'),default='source',help='Explicitly rebase captions to first video PTS; raw source captions retained')
    extract.add_argument('--out',type=Path,required=True)
    compose = commands.add_parser('compose',help='Mux generated speech with local video for one-clock playback')
    compose.add_argument('source',type=Path)
    compose.add_argument('run',type=Path)
    compose.add_argument('--out',type=Path,required=True)
    compose.add_argument('--background',type=Path,help='Explicitly supplied instrumental/permissioned WAV bed')
    compose.add_argument('--background-gain',type=float,default=.15)
    compose.add_argument('--transcode-video',action='store_true',help='Explicit CPU H.264 conversion instead of streamcopy')
    compose.add_argument('--clock',choices=('source','video'),default='source',help='With video clock, render cues must already be relative to first video PTS')
    media_checker = commands.add_parser('validate-media',help='Check extracted caption or playback artifact hashes')
    media_checker.add_argument('run',type=Path)
    reviewer = commands.add_parser('serve',help='Serve local review audio/video with HTTP Range support')
    reviewer.add_argument('directory',type=Path)
    reviewer.add_argument('--port',type=int,default=18576)
    comparison = commands.add_parser('compare',help='Make a listening set from same-corpus render runs')
    comparison.add_argument('runs',type=Path,nargs='+')
    comparison.add_argument('--label',action='append')
    comparison.add_argument('--first-cues',type=int,help='Short review excerpt retaining all selected utterances')
    comparison.add_argument('--out',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'speak':
            from contextlib import redirect_stdout
            from .speech import speak
            text = sys.stdin.read(20001) if args.text_file == '-' else Path(args.text_file).read_text(encoding='utf-8')
            # Optional model libraries print progress; keep stdout machine-readable.
            with redirect_stdout(sys.stderr):
                result = speak(text, args.out, engine_name=args.engine, voice=args.voice,
                               speed=args.speed, paragraph_pause_ms=args.paragraph_pause_ms,
                               threads=args.threads, model=args.model, model_dir=args.model_dir)
        elif args.command == "doctor":
            result = doctor()
        elif args.command == 'serve':
            from .review import serve
            serve(args.directory,args.port)
            return 0
        elif args.command == 'compare':
            from .review import build_comparison
            result = build_comparison(args.runs,args.out,args.label,args.first_cues)
        elif args.command == "inspect":
            result = {"source": str(args.source.resolve()), "summary": summary(load_cues(args.source))}
        elif args.command == "render":
            if args.out.exists():
                raise FileExistsError(f'Refusing to overwrite existing run: {args.out}')
            if args.engine not in ('piper-local','kokoro') and (args.cast or args.voice or args.speed != 1):
                raise ValueError('Casting and synthesis rate currently require a local speech engine')
            if args.engine == "tone":
                engine = ToneEngine()
            elif args.engine == "piper-http":
                engine = PiperHttpEngine(args.piper_url, args.speaker_id)
            elif args.engine in ('piper-local','kokoro'):
                from .local_tts import PiperLocalEngine, KokoroEngine
                plan = VoicePlan(VoiceSettings(voice=args.voice, speed=args.speed, speaker_id=args.speaker_id),args.cast)
                plan.validate_cues(load_cues(args.source))
                if args.engine == 'piper-local':
                    if not args.model:
                        parser.error('--model is required for piper-local')
                    engine = PiperLocalEngine(args.model,plan,args.threads)
                else:
                    engine = KokoroEngine(args.model_dir,plan,args.threads)
            else:
                if args.wav_dir is None:
                    parser.error("--wav-dir required with --engine wav-dir")
                engine = WavDirectoryEngine(args.wav_dir)
            result = render(args.source, args.out, engine, args.engine,fit_max_speedup=args.fit_max_speedup)
            print(f"Render artifacts: {args.out.resolve()}", file=sys.stderr)
            result = {"status": "RENDERED", "output": str(args.out.resolve()),
                      "metrics": result["metrics"], "warnings": result["warnings"]}
        elif args.command == 'validate':
            result = validate(args.run)
        else:
            from .media import probe,audit_captions,extract_captions,compose_video,validate_media
            if args.command == 'probe-media':result = probe(args.source)
            elif args.command == 'audit-captions':result = audit_captions(args.source,args.captions,clock=args.clock)
            elif args.command == 'extract':result = extract_captions(args.source,args.out,args.subtitle_index,clock=args.clock)
            elif args.command == 'compose':result = compose_video(args.source,args.run,args.out,
                background=args.background,background_gain=args.background_gain,transcode=args.transcode_video,clock=args.clock)
            else:result = validate_media(args.run)
        if getattr(args, "out", None) is not None and args.command in ('doctor','inspect','audit-captions'):
            args.out.parent.mkdir(parents=True, exist_ok=True)
            # diagnostics should not silently overwrite prior evidence
            with args.out.open("x", encoding="utf-8") as output:
                output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.command=='audit-captions' and result['status']=='FAIL' else 0
    except Exception as exc:
        print(f"ERROR [{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 1
