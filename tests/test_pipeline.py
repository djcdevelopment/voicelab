from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from subtitle_lab.audio import duration_ms, wav_frames
from subtitle_lab.pipeline import render, validate
from subtitle_lab.tts import ToneEngine, WavDirectoryEngine
from subtitle_lab.speech import paragraphs, speak

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


class RenderTests(unittest.TestCase):
    def test_plain_text_keeps_source_and_exact_paragraph_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = 'First line.\r\nStill first paragraph.\r\n \r\nCafé & <literal> text.\n\n'
            root = Path(tmp) / 'speech'
            result = speak(text, root, engine_name='tone', paragraph_pause_ms=350)
            self.assertEqual((root / 'source.txt').read_bytes(), text.encode())
            self.assertEqual([p['text'] for p in result['paragraphs']],
                             ['First line. Still first paragraph.', 'Café & <literal> text.'])
            self.assertEqual(result['metrics']['inserted_silence_ms'], 350)
            self.assertAlmostEqual(result['metrics']['audio_ms'], result['metrics']['speech_ms'] + 350)
            self.assertEqual(validate(root)['status'], 'PASS')
            _, _, _, raw = wav_frames(root / 'speech.wav')
            offset = 0
            for i, p in enumerate(result['paragraphs']):
                if i:
                    self.assertEqual(raw[offset:offset + 350 * 24 * 2], bytes(350 * 24 * 2))
                    offset += 350 * 24 * 2
                stem = wav_frames(root / p['stem'])[3]
                self.assertEqual(raw[offset:offset + len(stem)], stem)
                offset += len(stem)
            self.assertEqual(offset, len(raw))
            with self.assertRaises(FileExistsError):
                speak(text, root, engine_name='tone')

    def test_plain_text_rejects_invalid_requests_before_output(self):
        for value in ('', '  \n\n', 'x' * 5001, 'a\x00b'):
            with self.subTest(text=repr(value[:20])), self.assertRaises(ValueError):
                paragraphs(value)
        self.assertEqual(paragraphs('🙂' * 5000), ['🙂' * 5000])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'invalid'
            for settings in ({'speed':float('nan')}, {'speed':3}, {'paragraph_pause_ms':-1},
                             {'paragraph_pause_ms':True}, {'threads':0}, {'voice':'../../bad'}):
                with self.subTest(settings=settings), self.assertRaises(ValueError):
                    speak('Test', root, engine_name='tone', **settings)
                self.assertFalse(root.exists())

    def test_plain_text_tampering_and_failure_are_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'speech'
            speak('One.\n\nTwo.', root, engine_name='tone', paragraph_pause_ms=0)
            path = root / 'manifest.json'
            data = json.loads(path.read_text())
            data['paragraphs'][1]['start_sample'] += 1
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError): validate(root)
            # Missing dependencies are an explicit failed receipt, no fallback.
            failed = Path(tmp) / 'failed'
            with self.assertRaises(FileNotFoundError):
                speak('Test', failed, engine_name='kokoro', model_dir=Path(tmp) / 'absent')
            self.assertEqual(json.loads((failed / 'failure.json').read_text())['status'], 'failed')

    def test_end_to_end_tone_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "render"
            manifest = render(SAMPLES / "demo.srt", run, ToneEngine(), "tone")
            self.assertEqual(manifest["metrics"]["cue_count"], 5)
            self.assertTrue((run / "dub.wav").is_file())
            self.assertEqual(validate(run)["validated_files"], 10)
            self.assertGreater(duration_ms(run / "dub.wav"), 16000)
            self.assertEqual(wav_frames(run / "dub.wav")[0:3], (24000, 1, 2))
            with self.assertRaises(FileExistsError):
                render(SAMPLES / "demo.srt", run, ToneEngine(), "tone")

    def test_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "render"
            render(SAMPLES / "demo.srt", run, ToneEngine(), "tone")
            with (run / "stems" / "0001.wav").open("ab") as f:
                f.write(b"modified")
            with self.assertRaises(RuntimeError):
                validate(run)

    def test_wav_directory_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a = render(SAMPLES / "demo.srt", base / "tone", ToneEngine(), "tone")
            self.assertEqual(a["schema_version"], "subtitle-lab-render-v2")
            engine = WavDirectoryEngine(base / "tone" / "stems")
            render(SAMPLES / "demo.srt", base / "recomposed", engine, "wav-dir")
            self.assertEqual(validate(base / "recomposed")["validated_files"], 10)

    def test_overrun_is_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "tiny.srt"
            source.write_text("1\n00:00:00,100 --> 00:00:00,250\nThis line is much longer than that cue window.\n")
            run = Path(tmp) / "render"
            manifest = render(source, run, ToneEngine(), "tone")
            self.assertEqual(manifest["metrics"]["cue_overruns_gt_250ms"], 1)
            self.assertTrue(manifest["warnings"])

    def test_missing_external_stem_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                WavDirectoryEngine(Path(tmp) / "nonexistent")


if __name__ == "__main__":
    unittest.main()
