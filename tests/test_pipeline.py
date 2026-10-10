from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from subtitle_lab.audio import duration_ms, wav_frames
from subtitle_lab.pipeline import render, validate
from subtitle_lab.tts import ToneEngine, WavDirectoryEngine

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


class RenderTests(unittest.TestCase):
    def test_end_to_end_tone_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "render"
            manifest = render(SAMPLES / "demo.srt", run, ToneEngine(), "tone")
            self.assertEqual(manifest["metrics"]["cue_count"], 5)
            self.assertTrue((run / "dub.wav").is_file())
            self.assertEqual(validate(run)["validated_files"], 6)
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
            self.assertEqual(a["schema_version"], "subtitle-lab-render-v1")
            engine = WavDirectoryEngine(base / "tone" / "stems")
            render(SAMPLES / "demo.srt", base / "recomposed", engine, "wav-dir")
            self.assertEqual(validate(base / "recomposed")["validated_files"], 6)

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
