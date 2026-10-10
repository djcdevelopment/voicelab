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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Subtitle Lab local timed-text-to-audio R&D")
    commands = parser.add_subparsers(dest="command", required=True)
    diag = commands.add_parser("doctor", help="Read-only local Intel/GPU/tool discovery")
    diag.add_argument("--out", type=Path)
    inspect = commands.add_parser("inspect", help="Parse SRT/VTT/ASS and report cue stats")
    inspect.add_argument("source", type=Path)
    inspect.add_argument("--out", type=Path, help="Optional JSON report path")
    renderer = commands.add_parser("render", help="Generate stems, mixed WAV, and receipts")
    renderer.add_argument("source", type=Path)
    renderer.add_argument("--engine", choices=("tone", "piper-http", "wav-dir"), default="tone")
    renderer.add_argument("--out", type=Path, required=True, help="New output directory; never overwritten")
    renderer.add_argument("--piper-url", default="http://127.0.0.1:5000/synthesize")
    renderer.add_argument("--speaker-id", type=int)
    renderer.add_argument("--wav-dir", type=Path, help="Directory containing 0001.wav, 0002.wav, etc.")
    checker = commands.add_parser("validate", help="Verify SHA256 of rendered WAV and stems")
    checker.add_argument("run", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
        elif args.command == "inspect":
            result = {"source": str(args.source.resolve()), "summary": summary(load_cues(args.source))}
        elif args.command == "render":
            if args.engine == "tone":
                engine = ToneEngine()
            elif args.engine == "piper-http":
                engine = PiperHttpEngine(args.piper_url, args.speaker_id)
            else:
                if args.wav_dir is None:
                    parser.error("--wav-dir required with --engine wav-dir")
                engine = WavDirectoryEngine(args.wav_dir)
            result = render(args.source, args.out, engine, args.engine)
            print(f"Render artifacts: {args.out.resolve()}", file=sys.stderr)
            result = {"status": "RENDERED", "output": str(args.out.resolve()),
                      "metrics": result["metrics"], "warnings": result["warnings"]}
        else:
            result = validate(args.run)
        if getattr(args, "out", None) is not None and args.command != "render":
            args.out.parent.mkdir(parents=True, exist_ok=True)
            # diagnostics should not silently overwrite prior evidence
            with args.out.open("x", encoding="utf-8") as output:
                output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR [{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 1
